import pyodbc
from datetime import datetime, timedelta, date
from fpdf import FPDF
from PIL import Image
import os

# Define connection string
conn_str = (
    r'DRIVER={ODBC Driver 18 for SQL Server};'
    r'SERVER=(localdb)\Local;'
    r'DATABASE=master;'
    r'TRUSTED_CONNECTION=yes;'
)

def get_db_connection():
    return pyodbc.connect(conn_str)

def calculate_total_time(name_and_surname, date_str):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT event_type, time 
        FROM Events 
        WHERE name_and_surname = ? AND date = ?
        ORDER BY time
    """, name_and_surname, date_str)
    
    events = cursor.fetchall()
    conn.close()

    total_time = timedelta()
    day_start = datetime.combine(datetime.strptime(date_str, '%Y-%m-%d'), datetime.min.time())
    day_end = datetime.combine(datetime.strptime(date_str, '%Y-%m-%d'), datetime.max.time())
    
    if events and events[0][0] == 'exit':
        first_exit_time = datetime.combine(datetime.strptime(date_str, '%Y-%m-%d'), events[0][1])
        total_time += first_exit_time - day_start
        events = events[1:]

    if events and events[-1][0] == 'entry':
        last_entry_time = datetime.combine(datetime.strptime(date_str, '%Y-%m-%d'), events[-1][1])
        exit_time = datetime.now() if date_str == datetime.now().date().strftime('%Y-%m-%d') else day_end
        total_time += exit_time - last_entry_time
        events = events[:-1]
    
    entry_time = None
    for i in range(0, len(events), 2):
        if events[i][0] == 'entry':
            entry_time = datetime.combine(datetime.strptime(date_str, '%Y-%m-%d'), events[i][1])
            if i + 1 < len(events) and events[i + 1][0] == 'exit':
                exit_time = datetime.combine(datetime.strptime(date_str, '%Y-%m-%d'), events[i + 1][1])
                total_time += exit_time - entry_time
        elif events[i][0] == 'exit':
            exit_time = datetime.combine(datetime.strptime(date_str, '%Y-%m-%d'), events[i][1])
            if entry_time:
                total_time += exit_time - entry_time
                entry_time = None

    return total_time

def calculate_statistics_for_month(name_and_surname, year, month):
    total_month_time = timedelta()
    total_work_days = 0
    total_overtime = timedelta()
    total_undertime = timedelta()
    start_date = date(year, month, 1)
    
    while start_date.month == month:
        day_total = calculate_total_time(name_and_surname, start_date.strftime('%Y-%m-%d'))
        
        if day_total > timedelta(0):
            total_work_days += 1
            total_month_time += day_total
            
            workday_overtime = day_total - timedelta(hours=8)
            if workday_overtime > timedelta(0):
                total_overtime += workday_overtime

            workday_undertime = day_total - timedelta(hours=8)
            if workday_undertime < timedelta(0):
                total_undertime += workday_undertime

        start_date += timedelta(days=1)
    
    total_hours = total_month_time.total_seconds() / 3600
    average_time_per_day = total_hours / total_work_days if total_work_days > 0 else 0
    overtime_hours = total_overtime.total_seconds() / 3600
    undertime_hours = total_undertime.total_seconds() / 3600
    
    return total_hours, total_work_days, average_time_per_day, overtime_hours, undertime_hours

def fetch_worker_data(worker_id, year, month):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT name_and_surname, department, email, contact, foto_location FROM Workers WHERE id = ?", worker_id)
    worker_data = cursor.fetchone()
    
    start_date = date(year, month, 1)
    end_date = (start_date + timedelta(days=31)).replace(day=1) - timedelta(days=1)
    
    cursor.execute("""
        SELECT event_type, date, time 
        FROM Events 
        WHERE name_and_surname = ? AND date BETWEEN ? AND ?
        ORDER BY date, time
    """, worker_data[0], start_date, end_date)
    
    events = cursor.fetchall()
    
    conn.close()
    return worker_data, events

class PDF(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 14)
        self.set_text_color(0, 51, 102)
        self.cell(0, 10, 'Worker Report', 0, 1, 'C')
        self.ln(5)
    
    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Page {self.page_no()}', 0, 0, 'C')

def create_pdf(worker_data, events, stats, year, month):
    total_hours_in_month, total_work_days, average_time_per_day, overtime_hours, undertime_hours = stats
    pdf = PDF()
    pdf.add_page()

    # Worker Details
    pdf.set_fill_color(240, 240, 240)
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 10, txt="Worker Details", ln=True, align='L', fill=True)
    pdf.ln(5)

    foto_path = f"static/{worker_data[4]}"
    if foto_path and os.path.exists(foto_path):
        image = Image.open(foto_path)
        if image.mode == 'RGBA':
            image = image.convert('RGB')
        image = image.resize((75, 75), Image.LANCZOS)
        image.save("static/temp_image.jpg", quality=100)
        # Align image to the right and vertically centered with the text
        y_before = pdf.get_y()
        pdf.image("static/temp_image.jpg", x=150, y=y_before-2, w=45, h=50)
        pdf.set_y(y_before)

    pdf.set_font("Arial", 'B', 12)
    pdf.cell(40, 10, txt="Name:", align='L')
    pdf.cell(100, 10, txt=worker_data[0], ln=True)
    pdf.cell(40, 10, txt="Department:", align='L')
    pdf.cell(100, 10, txt=worker_data[1], ln=True)
    pdf.cell(40, 10, txt="Email:", align='L')
    pdf.cell(100, 10, txt=worker_data[2], ln=True)
    pdf.cell(40, 10, txt="Contact:", align='L')
    pdf.cell(100, 10, txt=worker_data[3], ln=True)

    # Add a line separator
    pdf.ln(10)
    pdf.set_y(pdf.get_y())
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 0, '', 0, 1, 'C')
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(10)

    # Monthly Statistics
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 10, txt="Monthly Statistics", ln=True, align='L')
    pdf.set_font("Arial", size=12)
    pdf.cell(0, 10, txt=f"Total hours for the month: {total_hours_in_month:.2f} hours.", ln=True)
    pdf.cell(0, 10, txt=f"Number of work days: {total_work_days}", ln=True)
    pdf.cell(0, 10, txt=f"Average time per day: {average_time_per_day:.2f} hours.", ln=True)
    pdf.cell(0, 10, txt=f"Overtime hours: {overtime_hours:.2f} hours.", ln=True)
    pdf.cell(0, 10, txt=f"Undertime hours: {undertime_hours:.2f} hours.", ln=True)

    pdf.ln(20)

    # Event Table
    pdf.set_font("Arial", 'B', 12)
    pdf.set_fill_color(200, 220, 255)
    pdf.cell(60, 10, txt="Event Type", border=1, align='C', fill=True)
    pdf.cell(65, 10, txt="Date", border=1, align='C', fill=True)
    pdf.cell(65, 10, txt="Time", border=1, align='C', fill=True)
    pdf.ln()

    pdf.set_font("Arial", size=12)
    fill = False
    for event in events:
        pdf.cell(60, 10, txt=f"{event[0]}", border=1, align='C', fill=fill)
        pdf.cell(65, 10, txt=f"{event[1]}", border=1, align='C', fill=fill)
        pdf.cell(65, 10, txt=f"{event[2]}", border=1, align='C', fill=fill)
        pdf.ln()
        fill = not fill
    
    pdf.ln(10)
    pdf.output(f"static/pdf_files/{worker_data[0]}_report_{month}_{year}.pdf")
    return f"static/pdf_files/{worker_data[0]}_report_{month}_{year}.pdf"

def create_pdf_file(worker_id, year, month):
    worker_data, events = fetch_worker_data(worker_id, year, month)
    stats = calculate_statistics_for_month(worker_data[0], year, month)
    file_path = create_pdf(worker_data, events, stats, year, month)
    print("PDF created successfully.")
    return file_path

if __name__ == "__main__":
    worker_id = 9  # Replace with the actual worker ID you want to fetch
    year = 2024
    month = 8
    create_pdf_file(worker_id, year, month)
