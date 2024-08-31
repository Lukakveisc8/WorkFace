import pyodbc
from datetime import datetime

# Definirajte konekcijski string
conn_str = (
    r'DRIVER={ODBC Driver 18 for SQL Server};'
    r'SERVER=(localdb)\Local;'
    r'DATABASE=master;'  # Zamijenite s nazivom vaše baze podataka
    r'TRUSTED_CONNECTION=yes;'
)

# Povežite se na SQL Server
mydb = pyodbc.connect(conn_str)

def get_status(name):
    # Kreiranje kursora
    mycursor = mydb.cursor()

    sql = "SELECT status FROM Workers WHERE name_and_surname = ?"
    val = (name,)
    mycursor.execute(sql, val)

    # Ispis svih redaka
    myresult = mycursor.fetchall()

    if myresult:
        # Uzimamo prvi (i jedini) tuple iz rezultata i pristupamo vrijednosti statusa
        status = myresult[0][0]
        
        print(status)
        return status

def set_status(name, status):
    # Kreiranje kursora
    mycursor = mydb.cursor()

    sql = "UPDATE Workers SET status = ? WHERE name_and_surname = ?"
    val = (status, name)
    
    try:
        mycursor.execute(sql, val)
        mydb.commit()
        print("Status uspješno ažuriran!")
    except pyodbc.Error as error:
        print(f"Greška prilikom ažuriranja statusa: {error}")

def enter_event(name, event):
    mycursor = mydb.cursor()

    # Trenutni datum i vrijeme
    now = datetime.now()
    date = now.strftime("%Y-%m-%d")
    time = now.strftime("%H:%M:%S")

    sql = "INSERT INTO Events (name_and_surname, event_type, date, time) VALUES (?, ?, ?, ?)"
    val = (name, event, date, time)

    try:
        mycursor.execute(sql, val)
        mydb.commit()
        print("Događaj uspješno dodan!")
    except pyodbc.Error as error:
        print(f"Greška prilikom dodavanja događaja: {error}")

def get_events(name):
    # Kreiranje kursora
    mycursor = mydb.cursor()

    sql = "SELECT * FROM Events WHERE name_and_surname = ?"
    val = (name,)
    mycursor.execute(sql, val)

    # Ispis svih redaka
    myresult = mycursor.fetchall()

    if myresult:
        # Ispis svih događaja za odabrano ime
        for row in myresult:
            print(row)
        
        return myresult
    else:
        print("Nema događaja za to ime.")
        return None

def get_informations(name):
    # Kreiranje kursora
    mycursor = mydb.cursor()

    sql = "SELECT * FROM Workers WHERE name_and_surname = ?"
    val = (name,)
    mycursor.execute(sql, val)

    # Ispis svih redaka
    myresult = mycursor.fetchall()

    if myresult:
        # Ispis svih informacija za odabrano ime
        for row in myresult:
            print(row)
        
        return myresult
    else:
        print("Nema podataka za to ime.")
        return None

def main():
    get_informations("Luka Kvesic")

if __name__ == "__main__":
    main()
