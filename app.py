from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from database import get_connection
import datetime

app = Flask(__name__)
app.secret_key = "smartcare_secret_key"


@app.route("/")
def index():
    return render_template("index.html")

# Login and Logout System


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username").strip()
        password = request.form.get("password")

        conn = get_connection()
        if conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT UserID, Username, PasswordHash FROM Users WHERE Username COLLATE Latin1_General_CS_AS = ?", (username,))
            user = cursor.fetchone()
            conn.close()

            if user:
                stored = user[2]
                if stored.startswith("scrypt:") or stored.startswith("pbkdf2:") or stored.startswith("sha256:"):
                    valid = check_password_hash(stored, password)
                else:
                    valid = (stored == password)

                if valid:
                    session["user"] = user[1]
                    return redirect(url_for("dashboard"))

            flash("Invalid username or password.", "error")
        else:
            flash("Database connection failed.", "error")

    return render_template("login.html")


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form.get("username").strip()
        password = request.form.get("password")
        confirm_password = request.form.get("confirm_password")

        if not username or not password:
            flash("Username and password are required.", "error")
            return render_template("signup.html")

        if password != confirm_password:
            flash("Passwords do not match.", "error")
            return render_template("signup.html")

        conn = get_connection()
        if conn:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    "SELECT UserID FROM Users WHERE Username COLLATE Latin1_General_CS_AS = ?", (username,))
                if cursor.fetchone():
                    conn.close()
                    flash("That username is already taken.", "error")
                    return render_template("signup.html")

                hashed = generate_password_hash(password)
                cursor.execute(
                    "INSERT INTO Users (Username, PasswordHash) VALUES (?, ?)",
                    (username, hashed))
                conn.commit()
                conn.close()
                flash("Account created successfully. Please sign in.", "success")
                return redirect(url_for("login"))
            except Exception as e:
                print("Error creating account:", e)
                conn.close()
                flash("Could not create account. Please try again.", "error")
        else:
            flash("Database connection failed.", "error")

    return render_template("signup.html")


@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect(url_for("login"))

# Patient Registration


@app.route("/register", methods=["GET", "POST"])
def register():
    if "user" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":
        patient_number = request.form.get("patient_number")
        sa_id = request.form.get("sa_id")
        first_name = request.form.get("first_name")
        last_name = request.form.get("last_name")
        dob = request.form.get("dob")
        gender = request.form.get("gender")
        contact_number = request.form.get("contact_number")
        email = request.form.get("email")
        residential_address = request.form.get("residential_address")
        emergency_contact = request.form.get("emergency_contact")
        registration_date = datetime.date.today().strftime('%Y-%m-%d')

        conn = get_connection()
        if conn:
            cursor = conn.cursor()
            query = """
                INSERT INTO Patients (
                    PatientNumber, 
                    IDNumber, 
                    FirstName, 
                    LastName, 
                    DateOfBirth, 
                    Gender, 
                    ContactNumber, 
                    Email, 
                    ResidentialAddress, 
                    EmergencyContact, 
                    RegistrationDate
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
            try:
                cursor.execute(query, (
                    patient_number,
                    sa_id,
                    first_name,
                    last_name,
                    dob,
                    gender,
                    contact_number,
                    email,
                    residential_address,
                    emergency_contact,
                    registration_date
                ))
                conn.commit()
                conn.close()
                flash("Patient registered successfully.", "success")
                return redirect(url_for("dashboard"))
            except Exception as e:
                print("Error registering patient:", e)
                conn.close()
                flash(
                    "Could not register patient. Check that the patient number and SA ID are unique.", "error")

    return render_template("register_patient.html")

# Appointment Booking


@app.route("/book_appointment", methods=["GET", "POST"])
def book_appointment():
    if "user" not in session:
        return redirect(url_for("login"))

    conn = get_connection()
    if request.method == "POST":
        patient_number = request.form.get("patient_id")
        doctor_id = request.form.get("doctor_id")
        appointment_date = request.form.get("appointment_date")
        appointment_time = request.form.get("appointment_time")
        notes = request.form.get("notes")
        status = "Confirmed"

        if conn:
            cursor = conn.cursor()
            query = """
                INSERT INTO Appointments (AppointmentDate, AppointmentTime, DoctorID, PatientNumber, AppointmentStatus, Notes)
                VALUES (?, ?, ?, ?, ?, ?)
            """
            cursor.execute(query, (appointment_date, appointment_time,
                           doctor_id, patient_number, status, notes))
            conn.commit()
            conn.close()
            return redirect(url_for("dashboard"))

    # Fetch patients and doctors for dropdown options
    patients = []
    doctors = []
    if conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT PatientNumber, FirstName, LastName, RegistrationDate FROM Patients ORDER BY RegistrationDate DESC, PatientNumber DESC")
        patients = cursor.fetchall()

        cursor.execute(
            "SELECT DoctorID, FullName, Specialisation FROM Doctors")
        doctors = cursor.fetchall()
        conn.close()

    return render_template("book_appointment.html", patients=patients, doctors=doctors)

# Dashboard


@app.route("/dashboard")
def dashboard():
    if "user" not in session:
        return redirect(url_for("login"))

    conn = get_connection()
    patient_count = 0
    doctor_count = 0
    total_appointments = 0
    today_count = 0
    upcoming_appointments = []

    if conn:
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM Patients")
        patient_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM Doctors")
        doctor_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM Appointments")
        total_appointments = cursor.fetchone()[0]

        today = datetime.date.today().strftime('%Y-%m-%d')
        cursor.execute(
            "SELECT COUNT(*) FROM Appointments WHERE AppointmentDate = ?", (today,))
        today_count = cursor.fetchone()[0]

        query_upcoming = """
            SELECT TOP 5 a.AppointmentNumber, a.AppointmentDate, a.AppointmentTime,
                   p.FirstName + ' ' + p.LastName AS PatientName,
                   d.FullName AS DoctorName, a.AppointmentStatus
            FROM Appointments a
            JOIN Patients p ON a.PatientNumber = p.PatientNumber
            JOIN Doctors d ON a.DoctorID = d.DoctorID
            WHERE a.AppointmentDate >= ?
            ORDER BY a.AppointmentDate ASC, a.AppointmentTime ASC
        """
        cursor.execute(query_upcoming, (today,))
        upcoming_appointments = cursor.fetchall()
        conn.close()

    return render_template("dashboard.html",
                           patient_count=patient_count,
                           doctor_count=doctor_count,
                           total_appointments=total_appointments,
                           today_count=today_count,
                           upcoming_appointments=upcoming_appointments)


# all Appointments


@app.route("/appointments")
def appointments():
    if "user" not in session:
        return redirect(url_for("login"))

    conn = get_connection()
    all_appointments = []

    if conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT a.AppointmentNumber, a.AppointmentDate, a.AppointmentTime,
                   p.FirstName + ' ' + p.LastName AS PatientName,
                   d.FullName AS DoctorName, d.Specialisation, a.AppointmentStatus, a.Notes
            FROM Appointments a
            JOIN Patients p ON a.PatientNumber = p.PatientNumber
            JOIN Doctors d ON a.DoctorID = d.DoctorID
            ORDER BY a.AppointmentDate DESC, a.AppointmentTime DESC
        """)
        all_appointments = cursor.fetchall()
        conn.close()

    return render_template("all_appointments.html", appointments=all_appointments)


if __name__ == "__main__":
    app.run(debug=True)
