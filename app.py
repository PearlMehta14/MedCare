
import sqlite3
import os
from flask import Flask, render_template, request, redirect, url_for, session
from werkzeug.security import generate_password_hash, check_password_hash
import smtplib
from email.mime.text import MIMEText

app = Flask(__name__)
app.secret_key = 'your_secret_key'

DB_PATH = os.path.join(app.instance_path, 'doctor_appointment.db')

if not os.path.exists(app.instance_path):
    os.makedirs(app.instance_path)

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

from datetime import datetime

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS usertable (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS doctorlogin (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            Email TEXT UNIQUE NOT NULL,
            Password TEXT NOT NULL
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS contact (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL,
            message TEXT NOT NULL
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS app (
            Sno INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            age INTEGER,
            address TEXT,
            phone TEXT,
            time TEXT,
            date TEXT,
            msg TEXT,
            status TEXT DEFAULT 'Confirmed'
        )
    ''')
    
    # Check if status column exists (for existing DBs)
    cursor.execute("PRAGMA table_info(app)")
    columns = [column[1] for column in cursor.fetchall()]
    if 'status' not in columns:
        cursor.execute("ALTER TABLE app ADD COLUMN status TEXT DEFAULT 'Confirmed'")

    # Check if a doctor exists, if not add a default one
    cursor.execute('SELECT * FROM doctorlogin WHERE Email = ?', ('doctor@example.com',))
    if not cursor.fetchone():
        hashed_password = generate_password_hash('password123')
        cursor.execute('INSERT INTO doctorlogin (Email, Password) VALUES (?, ?)', ('doctor@example.com', hashed_password))
    
    # Add a test patient
    cursor.execute('SELECT * FROM usertable WHERE email = ?', ('patient@example.com',))
    if not cursor.fetchone():
        hashed_password = generate_password_hash('patient123')
        cursor.execute('INSERT INTO usertable (email, password) VALUES (?, ?)', ('patient@example.com', hashed_password))
        
        # Add a test appointment for today
        today = datetime.now().strftime('%Y-%m-%d')
        cursor.execute("INSERT INTO app (name, age, address, phone, time, date, msg, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                       ('John Doe', 30, '123 Test St', '555-0199', '10:00', today, 'patient@example.com', 'Confirmed'))
    
    conn.commit()
    conn.close()

init_db()

@app.route("/")
def main():
    if 'loggedin' in session:
        return redirect(url_for('m'))
    return render_template('index.html')

@app.route("/home.html")
def m():
    if 'loggedin' not in session:
        return redirect(url_for('login'))
    return render_template('home.html')

@app.route("/api/upcoming_appointments")
def upcoming_appointments():
    if 'loggedin' not in session or 'email' not in session:
        return {"appointments": []}
    
    conn = get_db_connection()
    cursor = conn.cursor()
    today = datetime.now().strftime('%Y-%m-%d')
    cursor.execute("SELECT Sno, time, date, status FROM app WHERE msg = ? AND date = ? AND status = 'Confirmed'", (session['email'], today))
    appointments = cursor.fetchall()
    conn.close()
    
    upcoming = []
    now = datetime.now()
    for appt in appointments:
        try:
            appt_time = datetime.strptime(f"{appt['date']} {appt['time']}", "%Y-%m-%d %H:%M")
            diff = (appt_time - now).total_seconds() / 60
            if 0 < diff <= 15:
                upcoming.append({"time": appt['time'], "id": appt['Sno']})
        except:
            continue
            
    return {"appointments": upcoming}

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for('main'))

@app.route("/index.html")
def i():
    return redirect(url_for('main'))

@app.route("/about.html")
def abt():
    return render_template("about.html")

@app.route("/contactus.html", methods=['GET','POST'])
def submit_review():
    if request.method == 'POST':
        email = request.form['email']
        rating = request.form['message']
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO contact (email, message) VALUES (?, ?)", (email, rating))
        conn.commit()
        conn.close()
        return render_template('contactus.html', msg="Feedback received!")
    return render_template('contactus.html')

@app.route("/login.html", methods=['GET', 'POST'])
def logindr():
    if request.method == 'POST' and 'Email' in request.form and 'Password' in request.form:
        email = request.form['Email']
        password = request.form['Password']
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM doctorlogin WHERE Email = ?', (email,))
        account = cursor.fetchone()
        conn.close()
        if account and check_password_hash(account['Password'], password):
            session['loggedin'] = True
            session['Email'] = account['Email']
            session['role'] = 'doctor'
            return redirect(url_for('doctor_dashboard'))
        else:
            msg = 'Incorrect email/password!'
            return render_template('login.html', msg=msg)
    return render_template('login.html')

@app.route('/singup.html', methods=['GET', 'POST'])
def signupdr():
    if request.method == 'POST' and 'Email' in request.form and 'Password' in request.form:
        email = request.form['Email']
        password = generate_password_hash(request.form['Password'])
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM doctorlogin WHERE Email = ?', (email,))
        account = cursor.fetchone()
        if account:
            msg = 'Account already exists!'
            conn.close()
            return render_template('singup.html', msg=msg)
        else:
            cursor.execute('INSERT INTO doctorlogin (Email, Password) VALUES (?, ?)', (email, password))
            conn.commit()
            conn.close()
            return redirect(url_for('logindr'))
    return render_template('singup.html')

@app.route('/confirmation.html')
def confirmation():
    if 'loggedin' not in session: return redirect(url_for('login'))
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        # Show all appointments for this user to allow tracking and cancellation
        cursor.execute("SELECT * FROM app WHERE msg = ? ORDER BY date DESC, time DESC", (session.get('email'),))
        appointments = cursor.fetchall()
        conn.close()
        return render_template('confirmation.html', appointments=appointments)
    except Exception as e:
        return str(e)

@app.route('/cancel_appointment/<int:sno>')
def cancel_appointment(sno):
    if 'loggedin' not in session: return redirect(url_for('login'))
    conn = get_db_connection()
    cursor = conn.cursor()
    # Ensure patient can only cancel their own appointment
    cursor.execute("UPDATE app SET status = 'Cancelled' WHERE Sno = ? AND msg = ?", (sno, session.get('email')))
    conn.commit()
    conn.close()
    return redirect(url_for('confirmation'))

@app.route('/drdash.html')
def doctor_dashboard():
    if session.get('role') != 'doctor': return redirect(url_for('logindr'))
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM app WHERE status = 'Confirmed' ORDER BY date, time")
        appointments = cursor.fetchall()
        conn.close()
        return render_template('drdash.html', appointments=appointments)
    except Exception as e:
        return str(e)

@app.route('/patients.html')
def patients():
    if session.get('role') != 'doctor': return redirect(url_for('logindr'))
    search_query = request.args.get('search', '')
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        if search_query:
            query = "SELECT Sno, name, phone, status FROM app WHERE (name LIKE ? OR phone LIKE ?) ORDER BY name"
            cursor.execute(query, (f'%{search_query}%', f'%{search_query}%'))
        else:
            cursor.execute("SELECT Sno, name, phone, status FROM app ORDER BY name")
        appointments = cursor.fetchall()
        conn.close()
        return render_template('patients.html', appointments=appointments, search_query=search_query)
    except Exception as e:
        error_msg = f"Error fetching appointments: {str(e)}"
        return render_template('patients.html', appointments=[], error=error_msg)

@app.route("/consultation.html", methods=['GET', 'POST'])
def consultation():
    if 'loggedin' not in session: return redirect(url_for('login'))
    today_str = datetime.now().strftime('%Y-%m-%d')
    if request.method == 'POST':
        name = request.form.get('Name')
        age = request.form.get('Age')
        address = request.form.get('Address')
        phone = request.form.get('Phone')
        time = request.form.get('time')
        date = request.form.get('date')
        message = request.form.get('msg')
        
        # Validation
        now = datetime.now()
        selected_datetime = datetime.strptime(f"{date} {time}", "%Y-%m-%d %H:%M")
        
        if selected_datetime < now:
            return "<script>alert('Invalid Date/Time. Please select a future slot.'); window.history.back();</script>"

        conn = get_db_connection()
        cursor = conn.cursor()
        # Only check against 'Confirmed' appointments
        cursor.execute("SELECT * FROM app WHERE date = ? AND time = ? AND status = 'Confirmed'", (date, time))
        result = cursor.fetchone()

        if result:
            conn.close()
            return "<script>alert('Sorry, this time slot is already reserved.'); window.history.back();</script>"
        else:
            cursor.execute("INSERT INTO app (name, age, address, phone, time, date, msg, status) VALUES (?, ?, ?, ?, ?, ?, ?, 'Confirmed')",
                           (name, age, address, phone, time, date, message))
            conn.commit()
            conn.close()
            return redirect(url_for('confirmation'))
    return render_template('consultation.html', today=today_str)

@app.route("/timeslot.html")
def ts():
    selected_date = request.args.get('date', datetime.now().strftime('%Y-%m-%d'))
    is_sunday = datetime.strptime(selected_date, '%Y-%m-%d').weekday() == 6
    conn = get_db_connection()
    cursor = conn.cursor()
    # Only show 'Confirmed' slots as booked
    cursor.execute("SELECT time FROM app WHERE date = ? AND status = 'Confirmed'", (selected_date,))
    booked_slots = [row['time'] for row in cursor.fetchall()]
    conn.close()
    return render_template("timeslot.html", booked_slots=booked_slots, selected_date=selected_date, is_sunday=is_sunday)

@app.route("/loginp.html", methods=['GET', 'POST'])
def login():
    if request.method == 'POST' and 'email' in request.form and 'password' in request.form:
        email = request.form['email']
        password = request.form['password']
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM usertable WHERE email = ?', (email,))
        account = cursor.fetchone()
        conn.close()
        if account and check_password_hash(account['password'], password):
            session['loggedin'] = True
            session['email'] = account['email']
            return redirect(url_for('m'))
        else:
            msg = 'Incorrect email/password!'
            return render_template('loginp.html', msg=msg)
    return render_template('loginp.html')

@app.route('/singuppt.html', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST' and 'email' in request.form and 'password' in request.form:
        email = request.form['email']
        password = generate_password_hash(request.form['password'])
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM usertable WHERE email = ?', (email,))
        account = cursor.fetchone()
        if account:
            msg = 'Account already exists!'
            conn.close()
            return render_template('singuppt.html', msg=msg)
        else:
            cursor.execute('INSERT INTO usertable (email, password) VALUES (?, ?)', (email, password))
            conn.commit()
            conn.close()
            return redirect(url_for('login'))
    return render_template('singuppt.html')

if __name__ == '__main__':
    app.run(debug=True)


