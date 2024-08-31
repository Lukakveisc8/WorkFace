from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, Response, send_file
import pyodbc
import cv2
from database import get_status,set_status, enter_event
from simple_facerec import SimpleFacerec
import json
import os
from werkzeug.utils import secure_filename
from pdf import create_pdf_file

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Replace with a secure key

conn_str = (
    r'DRIVER={ODBC Driver 18 for SQL Server};'
    r'SERVER=(localdb)\Local;'
    r'DATABASE=master;'
    r'Trusted_Connection=yes;'
)

conn = pyodbc.connect(conn_str)
cursor = conn.cursor()
cursor.execute("SELECT company_name FROM Settings WHERE id = 1;")

company_name = cursor.fetchone()[0]

# Define global variable for new events
new_event = False

    
@app.route('/')
def home():
    return render_template('login.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        conn = pyodbc.connect(conn_str)
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM Bosses WHERE email = ? AND password = ?", (email, password))
        user = cursor.fetchone()

        if user:
            session['loggedin'] = True
            session['email'] = user.email
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid email or password', 'danger')
        
        cursor.close()
        conn.close()

    return render_template('login.html')


#Dio za dashboard
#################  
@app.route('/dashboard')
def dashboard():

    if 'loggedin' not in session or not session['loggedin']:
        return redirect(url_for('login'))

    return render_template('dashboard.html', company_name=company_name)

@app.route('/api/workers')
def api_workers():
    conn = pyodbc.connect(conn_str)
    cursor = conn.cursor()

    cursor.execute("SELECT id, name_and_surname, department, status, foto_location FROM Workers")
    workers = cursor.fetchall()

    # Pretvaranje rezultata u JSON
    workers_list = []
    for worker in workers:
        workers_list.append({
            'id': worker.id,
            'name_and_surname': worker.name_and_surname,
            'department': worker.department,
            'status': worker.status,
            'foto_location': worker.foto_location
        })

    cursor.close()
    conn.close()

    return jsonify(workers_list)

@app.route('/api/events')
def api_events():
    conn = pyodbc.connect(conn_str)
    cursor = conn.cursor()

    cursor.execute("SELECT name_and_surname, event_type, date, time FROM Events ORDER BY date DESC, time DESC")
    events = cursor.fetchall()

    # Pretvaranje rezultata u JSON
    events_list = []
    for event in events:
        events_list.append({
            'name_and_surname': event.name_and_surname,
            'event_type': event.event_type,
            'date': event.date.strftime('%Y-%m-%d'),
            'time': event.time.strftime('%H:%M:%S')
        })

    cursor.close()
    conn.close()

    return jsonify(events_list)

@app.route('/api/new-events', methods=['GET'])
def new_events():
    global new_event
    new_events_available= False
    new_events_available = new_event
    if new_event:
        new_event = False
    return jsonify({'new_events': new_events_available})

#Dio za dodavanje radnika i njegov edit
#######################################

@app.route('/add_worker', methods=['GET', 'POST'])
def add_worker():
    if 'loggedin' not in session or not session['loggedin']:
        return redirect(url_for('login'))

    if request.method == 'POST':
        name = request.form.get('name')
        department = request.form.get('department')
        email = request.form.get('email')
        contact = request.form.get('contact')
        image = request.files['photo']

        

        # Check if all fields are provided
        if not all([name, department, email, contact, image]):
            flash('All fields are required!', 'danger')
            return redirect(request.url)

        # Save the image
        if image:
            filename = f"{name}.jpg"
            filepath = os.path.join("static/images", filename)
            image.save(filepath)

        print(filepath)

        # Save data to database
        conn = pyodbc.connect(conn_str)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO Workers (name_and_surname, department, email, status, contact, foto_location) VALUES (?, ?, ?, ?, ?, ?)",
            (name, department, email, 0, contact, f"images/{filename}")
        )
        conn.commit()  # Commit the transaction
        conn.close()   # Close the connection

        sfr.load_encoding_image(f"static/images/{filename}")
        return redirect(url_for('dashboard'))
    return render_template('add_worker.html', company_name=company_name)

@app.route('/worker/<int:worker_id>/remove', methods=['POST'])
def remove_worker(worker_id):
    if 'loggedin' not in session or not session['loggedin']:
        return redirect(url_for('login'))
    conn = pyodbc.connect(conn_str)
    cursor = conn.cursor()
        
    cursor.execute("SELECT * FROM Workers WHERE id = ?", (worker_id,))
    worker = cursor.fetchone()
        
    if worker:
        try:
            os.remove(os.path.join('static', worker.foto_location))
        except OSError:
            pass  # Ignore if file does not exist
            
        cursor.execute("DELETE FROM Workers WHERE id = ?", (worker_id,))
        conn.commit()
        cursor.execute("DELETE FROM Events WHERE name_and_surname = ?", (worker.name_and_surname,))
        conn.commit()

        cursor.close()
        conn.close()

    return redirect(url_for('dashboard'))

@app.route('/edit_worker/<int:worker_id>', methods=['GET', 'POST'])
def edit_worker(worker_id):
    if 'loggedin' not in session:
        flash('Please log in first', 'warning')
        return redirect(url_for('login'))

    conn = pyodbc.connect(conn_str)
    cursor = conn.cursor()

    # Retrieve existing worker data
    cursor.execute("SELECT * FROM Workers WHERE id = ?", (worker_id,))
    worker = cursor.fetchone()
    
    if worker is None:
        flash('Worker not found.', 'danger')
        cursor.close()
        conn.close()
        return redirect(url_for('dashboard'))

    old_name = worker.name_and_surname

    if request.method == 'POST':
        # Get form data
        name = request.form.get('name')
        department = request.form.get('department')
        email = request.form.get('email')
        contact = request.form.get('contact')
        photo = request.files.get('photo')

        if not (name and department and email and contact):
            flash('All fields are required.', 'danger')
            return redirect(url_for('edit_worker', worker_id=worker_id))

        # Handle photo upload
        photo_location = worker.foto_location
        if photo and photo.filename:
            filename = f"{name}.jpg"
            photo_path = os.path.join('static/images', filename)
            photo.save(photo_path)
            photo_location = f"images/{filename}"

        if not old_name==name:
            filename_remove = f"{old_name}.jpg"
            photo_path_remove = os.path.join('static/images', filename_remove)
            if os.path.exists(photo_path_remove):
                os.remove(photo_path_remove)


        # Update database
        try:
            # Update the name_and_surname in the Events table
            cursor.execute("""
                UPDATE Events
                SET name_and_surname = ?
                WHERE name_and_surname = ?
            """, (name, old_name))
            
            # Update Workers table
            cursor.execute("""
                UPDATE Workers
                SET name_and_surname = ?, department = ?, email = ?, contact = ?, foto_location = ?
                WHERE id = ?
            """, (name, department, email, contact, photo_location, worker_id))
            conn.commit()
        except Exception as e:
            conn.rollback()
            flash(f'Error updating worker: {e}', 'danger')
            cursor.close()
            conn.close()
            return redirect(url_for('edit_worker', worker_id=worker_id))
        finally:
            cursor.close()
            conn.close()

        flash('Worker details updated successfully!', 'success')

        # Optionally, update facial recognition system
        if photo and photo.filename:
            sfr.load_encoding_image(photo_path)
        
        return redirect(url_for('dashboard'))

    # Pre-fill the form with existing data
    return render_template('edit_worker.html', company_name=company_name, worker=worker)

@app.route('/<int:worker_id>/generate_pdf', methods=['POST'])
def generate_pdf(worker_id):
    try:
        year = int(request.form.get('year'))
        month = int(request.form.get('month'))

        # Call the function to create the PDF file
        file_path = create_pdf_file(worker_id, year, month)

        # Ensure the file exists before sending
        if not os.path.exists(file_path):
            return "File not found", 404

        # Send the file as a response
        return send_file(
            file_path,
            as_attachment=True,
            download_name=secure_filename(os.path.basename(file_path))
        )
    except Exception as e:
        return str(e), 500








#Dio za detekciju radnika
#########################

sfr = SimpleFacerec()

def gen_frames():
    cap = cv2.VideoCapture(1)  # Adjust the index as necessary

    if not cap.isOpened():
        print("Cannot open camera")
        exit()

    global entry_status, exit_status
    global new_event
    entry_status = False
    exit_status = False

    detected = False
    count = 60

    while True:
        success, frame = cap.read()
        if not success:
            break
        else:
            rotated_frame = cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)
            rotated_frame = cv2.flip(rotated_frame, 1)

            height, width = rotated_frame.shape[:2]
            rect_width = 240
            rect_height = 320

            top_left_x = (width - rect_width) // 2
            top_left_y = (height - rect_height) // 2
            bottom_right_x = top_left_x + rect_width
            bottom_right_y = top_left_y + rect_height

            cv2.rectangle(rotated_frame, (top_left_x, top_left_y-50), (bottom_right_x, bottom_right_y-50), (100, 0, 0), 2)

            if entry_status:
                status = 1
                face_locations, face_names = sfr.detect_known_faces(rotated_frame)
                for face_loc, name in zip(face_locations, face_names):
                    y1, x2, y2, x1 = face_loc[0], face_loc[1], face_loc[2], face_loc[3]
                        
                    if name != "Unknown":
                        if get_status(name) == 0:
                            set_status(name, status)
                            enter_event(name, "entry")
                        title = "Welcome"
                        detected = True
                        new_event = True
                        entry_status = False
                    else:
                        enter_event("Unknown", "entry")
                        title = "Unknown"
                        detected = True 
                        new_event = True
                        entry_status = False              
                    
            if exit_status:
                status = 0
                face_locations, face_names = sfr.detect_known_faces(rotated_frame)
                for face_loc, name in zip(face_locations, face_names):
                    y1, x2, y2, x1 = face_loc[0], face_loc[1], face_loc[2], face_loc[3]
                    if name != "Unknown":
                        if get_status(name) == 1:
                            set_status(name, status)
                            enter_event(name, "exit")
                        title = "Goodbye"
                        detected = True
                        new_event = True
                        exit_status = False
                    else:
                        enter_event("Unknown", "exit")
                        title = "Unknown"
                        detected = True   
                        new_event = True 
                        exit_status = False        

            if detected:
                if count > 0:
                    count -= 1
                    if title == "Unknown":
                        cv2.putText(rotated_frame, title, (top_left_x, top_left_y-60), cv2.FONT_HERSHEY_DUPLEX, 1, (0, 0, 255), 1)
                        cv2.putText(rotated_frame, name, (x1, y1 - 10), cv2.FONT_HERSHEY_DUPLEX, 1, (0, 0, 200), 2)
                        cv2.rectangle(rotated_frame, (x1, y1), (x2, y2), (0, 0, 200), 4)
                    else:
                        cv2.putText(rotated_frame, title, (top_left_x, top_left_y-60), cv2.FONT_HERSHEY_DUPLEX, 1, (0, 255, 0), 1)
                        cv2.putText(rotated_frame, name, (x1, y1 - 10), cv2.FONT_HERSHEY_DUPLEX, 1, (0, 0, 200), 2)
                        cv2.rectangle(rotated_frame, (x1, y1), (x2, y2), (0, 0, 200), 4)
                else:
                    detected = False
                    count = 60

            ret, buffer = cv2.imencode('.jpg', rotated_frame)
            frame = buffer.tobytes()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
                 
@app.route('/face_recognitioon', endpoint='face_recognitioon')
def face_recognition():
    if 'loggedin' not in session or not session['loggedin']:
        return redirect(url_for('login'))
    return render_template('index.html')

@app.route('/video_feed')
def video_feed():
    if 'loggedin' not in session or not session['loggedin']:
        return redirect(url_for('login'))
    return Response(gen_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/set_entry_status', methods = ['POST'])
def set_entry_status_route():
    global entry_status
    data = request.json
    if 'entry_status' in data:
        entry_status = True
    return jsonify({'status': 'success'})

@app.route('/set_exit_status', methods = ['POST'])
def set_exit_status_route():
    global exit_status
    data = request.json
    if 'exit_status' in data:
        exit_status = True
    return jsonify({'status': 'success'})




@app.route('/settings', methods=['GET', 'POST'])
def settings():
    global company_name
    if request.method == 'POST':
        company_name = request.form['company_name']

        conn = pyodbc.connect(conn_str)
        cursor = conn.cursor()

        cursor.execute("UPDATE Settings SET company_name = ? WHERE id = 1;", (company_name,))
        conn.commit()
        
        # Handle file upload
        if 'company_logo' in request.files:
            file = request.files['company_logo']
            if file and file.filename.endswith(('png', 'jpg', 'jpeg')):
                filename = 'logo.png'
                file.save(os.path.join('static', filename))
        
        return redirect(url_for('settings'))
    
    return render_template('settings.html', company_name=company_name)




@app.route('/logout')
def logout():
    # Brisanje svih podataka iz sesije
    session.clear()
    # Preusmeravanje na stranicu za prijavu ili početnu stranicu
    return redirect(url_for('login'))



#Dio za jednog radnika
######################

@app.route('/worker/<int:worker_id>')
def worker_detail(worker_id):
    # Ispisuje worker_id u konzolu
    print(f"Worker ID: {worker_id}")
    
    # Renderiraj template za prikaz detalja radnika
    return render_template('worker_detail.html', company_name=company_name, worker_id=worker_id)

@app.route('/api/events/<int:worker_id>', methods=['GET'])
def get_events(worker_id):
    conn = pyodbc.connect(conn_str)
    cursor = conn.cursor()

    # Get worker's name and surname
    cursor.execute("SELECT name_and_surname FROM Workers WHERE id = ? ", (worker_id,))
    worker_name_row = cursor.fetchone()  # Use fetchone() if expecting a single row

    if worker_name_row is None:
        return jsonify({'error': 'Worker not found'}), 404

    worker_name = worker_name_row[0]  # Extract the name_and_surname from the row

    # Get events for the worker
    cursor.execute("SELECT * FROM Events WHERE name_and_surname = ? ORDER BY date DESC, time DESC", (worker_name,))
    events = cursor.fetchall()

    # Convert results to JSON
    events_list = []
    for event in events:
        events_list.append({
            'name_and_surname': event.name_and_surname,
            'event_type': event.event_type,
            'date': event.date.strftime('%Y-%m-%d'),
            'time': event.time.strftime('%H:%M:%S')
        })
    
    cursor.close()
    conn.close()
    return jsonify(events_list)

@app.route('/api/worker/<int:worker_id>', methods=['GET'])
def get_worker(worker_id):
    conn = pyodbc.connect(conn_str)
    cursor = conn.cursor()

    # Get worker's details
    cursor.execute("SELECT name_and_surname, department, email, contact, status, foto_location FROM Workers WHERE id = ?", (worker_id,))
    worker_row = cursor.fetchone()  # Use fetchone() if expecting a single row

    if worker_row is None:
        return jsonify({'error': 'Worker not found'}), 404

    # Convert results to JSON
    worker = {
        'name_and_surname': worker_row.name_and_surname,
        'department': worker_row.department,
        'email': worker_row.email,
        'contact': worker_row.contact,
        'status': worker_row.status,
        'foto_location': worker_row.foto_location
    }
    
    cursor.close()
    conn.close()
    return jsonify(worker)







if __name__ == '__main__':
    sfr.load_encoding_images('C:/Users/Korisnik/Desktop/WorkFace/static/images')
    app.run(debug=True, host='0.0.0.0')
