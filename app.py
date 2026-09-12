from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from database import get_connection
import datetime
import hashlib

app = Flask(__name__)
app.secret_key = "smartcare_secret_key"


def fetch_rows(query, params=None, demo=None):
    """Run a SELECT against the live DB. Falls back to demo rows so the
    prototype still renders when the SQL Server database is unavailable."""
    conn = get_connection()
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute(query, params or ())
            rows = cursor.fetchall()
            if rows:
                return rows
        except Exception as e:
            print("DB query error:", e)
        finally:
            try:
                conn.close()
            except Exception:
                pass
    return demo or []


def fmt_date(d):
    if isinstance(d, datetime.date):
        return d.strftime("%Y-%m-%d")
    return str(d)


def fmt_time(t):
    if hasattr(t, "hour"):
        return t.strftime("%H:%M")
    return str(t)


# ---- Prototype demo data (used when the database is unreachable) -------

DEMO_DOCTORS = [
    (1, "Dr. Sarah Naidoo", "General Practitioner"),
    (2, "Dr. Kevin Mokoena", "Cardiologist"),
    (3, "Dr. Priya Reddy", "Dermatologist"),
    (4, "Dr. Thabo Ndlovu", "Pediatrician"),
    (5, "Dr. Amina Patel", "Gynaecologist"),
]

DEMO_PATIENTS = [
    ("90000125", "Lerato", "Mokoena", "1985-04-12", "Female", "082 555 0101",
     "lerato.m@gmail.com", "12 Main Road, Durban"),
    ("90000147", "Johan", "Venter", "1978-11-23", "Male", "083 555 0112",
     "jventer@gmail.com", "8 Oak Street, Pretoria"),
    ("90000158", "Naledi", "Khumalo", "1992-07-30", "Female", "079 555 0199",
     "naledi.k@icloud.com", "45 Acacia Avenue, Soweto"),
    ("90000162", "Pieter", "Du Toit", "1965-02-18", "Male", "084 555 0120",
     "pdt@telkom.co.za", "3 Cedar Lane, Cape Town"),
    ("90000173", "Aisha", "Daniels", "1998-09-03", "Female", "072 555 0144",
     "aisha.d@gmail.com", "27 Sunbird Close, Midrand"),
]

PATIENT_LOOKUP = {p[0]: p for p in DEMO_PATIENTS}

DOCTOR_SPEC = {d[1]: d[2] for d in DEMO_DOCTORS}


def demo_appointments():
    """Deterministic-but-live demo schedule around today's date."""
    today = datetime.date.today()
    d = lambda offset: (today + datetime.timedelta(days=offset)).strftime("%Y-%m-%d")
    return [
        (101, d(0), "09:30", "90000125", "Lerato Mokoena",
         "Dr. Sarah Naidoo", "Confirmed", "Follow-up on blood pressure"),
        (102, d(0), "11:00", "90000147", "Johan Venter",
         "Dr. Kevin Mokoena", "Confirmed", "Chest pain review"),
        (103, d(0), "14:45", "90000158", "Naledi Khumalo",
         "Dr. Priya Reddy", "Pending", "Skin rash consultation"),
        (104, d(1), "08:30", "90000162", "Pieter Du Toit",
         "Dr. Thabo Ndlovu", "Confirmed", "Annual check-up"),
        (105, d(1), "13:00", "90000125", "Lerato Mokoena",
         "Dr. Amina Patel", "Confirmed", "Antenatal scan"),
        (106, d(2), "10:15", "90000173", "Aisha Daniels",
         "Dr. Sarah Naidoo", "Confirmed", "Flu symptoms"),
        (107, d(-1), "10:00", "90000158", "Naledi Khumalo",
         "Dr. Sarah Naidoo", "Completed", "Blood test results"),
        (108, d(-2), "15:30", "90000147", "Johan Venter",
         "Dr. Priya Reddy", "Completed", "Dermatology consult"),
    ]


def demo_history(patient_number):
    patient = PATIENT_LOOKUP.get(patient_number, ("90000125", "Lerato", "Mokoena",
                                                  "1985-04-12", "Female", "082 555 0101",
                                                  "lerato.m@gmail.com", "12 Main Road, Durban"))
    today = datetime.date.today()
    d = lambda offset: (today + datetime.timedelta(days=offset)).strftime("%Y-%m-%d")
    return [
        (d(-1), "10:00", "Dr. Sarah Naidoo", "Completed",
         "Blood pressure elevated; prescribed moderate exercise."),
        (d(-30), "09:30", "Dr. Amina Patel", "Completed",
         "Annual wellness screening; all results within normal range."),
        (d(-90), "14:00", "Dr. Kevin Mokoena", "Completed",
         "Cardiac ECG review; no abnormalities detected."),
        (d(-210), "11:30", "Dr. Sarah Naidoo", "Completed",
         "Initial consultation: patient profile created."),
    ], "Penicillin", "Grass pollen", patient


def demo_reports():
    return {
        "by_specialisation": [
            ("General Practitioner", 14), ("Cardiologist", 7),
            ("Dermatologist", 6), ("Pediatrician", 5), ("Gynaecologist", 4)],
        "by_status": [("Confirmed", 12), ("Pending", 4), ("Completed", 18), ("Cancelled", 2)],
        "by_gender": [("Male", 23), ("Female", 31), ("Other", 0)],
    }


# ---- Landing / auth ----------------------------------------------------


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    remember_username = request.cookies.get("smartcare_username", "")

    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        remember = request.form.get("remember")

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
                    response = redirect(url_for("dashboard"))
                    if remember:
                        response.set_cookie(
                            "smartcare_username", username,
                            max_age=60 * 60 * 24 * 30, httponly=True)
                    else:
                        response.delete_cookie("smartcare_username")
                    return response

            flash("Invalid username or password.", "error")
        else:
            flash("Database connection failed.", "error")

    return render_template("login.html", remember_username=remember_username)


@app.route("/forgot_password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        email = (request.form.get("email") or "").strip()
        if not email:
            flash("Please enter your registered email address.", "error")
        else:
            flash("If an account exists for that address, a password reset link "
                  "has been sent. (Prototype simulation)", "success")
            return redirect(url_for("login"))
    return render_template("forgot_password.html")


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
            success = False
            try:
                cursor = conn.cursor()
                query = """
                    INSERT INTO Appointments (AppointmentDate, AppointmentTime, DoctorID, PatientNumber, AppointmentStatus, Notes)
                    VALUES (?, ?, ?, ?, ?, ?)
                """
                cursor.execute(query, (appointment_date, appointment_time,
                               doctor_id, patient_number, status, notes))
                conn.commit()
                success = True
            except Exception as e:
                print("Error booking appointment:", e)
                flash("Could not book appointment. Check the patient number and doctor selection.", "error")
            finally:
                try:
                    conn.close()
                except Exception:
                    pass
            if success:
                session["booking_confirmation"] = {
                    "number": patient_number,
                    "doctor": doctor_id,
                    "date": appointment_date,
                    "time": appointment_time,
                    "status": "Confirmed",
                }
                return redirect(url_for("booking_success"))

    # Fetch patients and doctors for dropdown options
    patients = fetch_rows(
        "SELECT PatientNumber, FirstName, LastName, RegistrationDate FROM Patients "
        "ORDER BY RegistrationDate DESC, PatientNumber DESC",
        demo=[(p[0], p[1], p[2], "2026-09-10") for p in DEMO_PATIENTS])
    doctors = fetch_rows(
        "SELECT DoctorID, FullName, Specialisation FROM Doctors",
        demo=DEMO_DOCTORS)

    if conn:
        try:
            conn.close()
        except Exception:
            pass

    return render_template("book_appointment.html", patients=patients, doctors=doctors)


@app.route("/booking_success")
def booking_success():
    if "user" not in session:
        return redirect(url_for("login"))
    confirmation = session.pop("booking_confirmation", None)
    if not confirmation:
        return redirect(url_for("dashboard"))
    return render_template("booking_success.html", confirmation=confirmation)

# Doctor Management


@app.route("/doctors")
def doctors():
    if "user" not in session:
        return redirect(url_for("login"))

    conn = get_connection()
    all_doctors = []

    if conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT DoctorID, FullName, Specialisation, PhoneNumber, Email FROM Doctors ORDER BY FullName")
        all_doctors = cursor.fetchall()
        conn.close()

    return render_template("all_doctors.html", doctors=all_doctors)


@app.route("/add_doctor", methods=["GET", "POST"])
def add_doctor():
    if "user" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":
        full_name = request.form.get("full_name").strip()
        specialisation = request.form.get("specialisation").strip()
        phone_number = request.form.get("phone_number").strip()
        email = request.form.get("email").strip()

        if not full_name or not specialisation:
            flash("Full name and specialisation are required.", "error")
            return render_template("add_doctor.html")

        conn = get_connection()
        if conn:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    "INSERT INTO Doctors (FullName, Specialisation, PhoneNumber, Email) VALUES (?, ?, ?, ?)",
                    (full_name, specialisation, phone_number or None, email or None))
                conn.commit()
                conn.close()
                flash("Doctor added successfully.", "success")
                return redirect(url_for("doctors"))
            except Exception as e:
                print("Error adding doctor:", e)
                conn.close()
                flash("Could not add doctor. Please try again.", "error")

    return render_template("add_doctor.html")


@app.route("/edit_doctor/<int:doctor_id>", methods=["GET", "POST"])
def edit_doctor(doctor_id):
    if "user" not in session:
        return redirect(url_for("login"))

    conn = get_connection()
    doctor = None

    if conn:
        cursor = conn.cursor()

        if request.method == "POST":
            full_name = request.form.get("full_name").strip()
            specialisation = request.form.get("specialisation").strip()
            phone_number = request.form.get("phone_number").strip()
            email = request.form.get("email").strip()

            if not full_name or not specialisation:
                flash("Full name and specialisation are required.", "error")
            else:
                try:
                    cursor.execute(
                        "UPDATE Doctors SET FullName = ?, Specialisation = ?, PhoneNumber = ?, Email = ? WHERE DoctorID = ?",
                        (full_name, specialisation, phone_number or None, email or None, doctor_id))
                    conn.commit()
                    conn.close()
                    flash("Doctor updated successfully.", "success")
                    return redirect(url_for("doctors"))
                except Exception as e:
                    print("Error updating doctor:", e)
                    flash("Could not update doctor. Please try again.", "error")

        cursor.execute(
            "SELECT DoctorID, FullName, Specialisation, PhoneNumber, Email FROM Doctors WHERE DoctorID = ?",
            (doctor_id,))
        doctor = cursor.fetchone()
        conn.close()

    if not doctor:
        flash("Doctor not found.", "error")
        return redirect(url_for("doctors"))

    return render_template("edit_doctor.html", doctor=doctor)


@app.route("/delete_doctor/<int:doctor_id>", methods=["POST"])
def delete_doctor(doctor_id):
    if "user" not in session:
        return redirect(url_for("login"))

    conn = get_connection()
    if conn:
        cursor = conn.cursor()
        try:
            cursor.execute("DELETE FROM Doctors WHERE DoctorID = ?", (doctor_id,))
            conn.commit()
            conn.close()
            flash("Doctor deleted successfully.", "success")
        except Exception as e:
            print("Error deleting doctor:", e)
            conn.close()
            flash("Could not delete doctor. They may have existing appointments.", "error")

    return redirect(url_for("doctors"))

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
    notifications = []

    today = datetime.date.today().strftime('%Y-%m-%d')
    new_this_week = 0

    if conn:
        cursor = conn.cursor()

        try:
            cursor.execute("SELECT COUNT(*) FROM Patients")
            patient_count = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM Doctors")
            doctor_count = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM Appointments")
            total_appointments = cursor.fetchone()[0]

            cursor.execute(
                "SELECT COUNT(*) FROM Appointments WHERE AppointmentDate = ?", (today,))
            today_count = cursor.fetchone()[0]

            cursor.execute(
                "SELECT COUNT(*) FROM Patients WHERE RegistrationDate >= DATEADD(day, -7, CAST(GETDATE() AS DATE))")
            new_this_week = cursor.fetchone()[0]

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
        except Exception as e:
            print("Dashboard query error:", e)
        finally:
            try:
                conn.close()
            except Exception:
                pass

        if today_count == 0 and not upcoming_appointments:
            # nothing useful in DB yet - fall back to demo schedule
            upcoming_appointments = []
            patient_count = len(DEMO_PATIENTS)
            doctor_count = len(DEMO_DOCTORS)
            total_appointments = len(demo_appointments())
            today_count = 0
    else:
        patient_count = len(DEMO_PATIENTS)
        doctor_count = len(DEMO_DOCTORS)
        total_appointments = len(demo_appointments())

    if today_count:
        notifications.append(("appointment",
                              "%d appointment(s) scheduled for today." % today_count))
    if not upcoming_appointments:
        notifications.append(("alert", "No upcoming appointments in the schedule."))
    else:
        nxt = upcoming_appointments[0]
        notifications.append((
            "info",
            "Next up: %s with %s on %s at %s." % (nxt[3], nxt[4], nxt[1], nxt[2])))
    if new_this_week:
        notifications.append(("success",
                              "%d new patient(s) registered in the last 7 days." % new_this_week))
    elif patient_count:
        notifications.append(("success",
                              "%d patient(s) currently registered." % patient_count))

    return render_template("dashboard.html",
                           patient_count=patient_count,
                           doctor_count=doctor_count,
                           total_appointments=total_appointments,
                           today_count=today_count,
                           upcoming_appointments=upcoming_appointments,
                           notifications=notifications)


# All Appointments


@app.route("/appointments")
def appointments():
    if "user" not in session:
        return redirect(url_for("login"))

    all_appointments = fetch_rows(
        """
        SELECT a.AppointmentNumber, a.AppointmentDate, a.AppointmentTime,
               p.FirstName + ' ' + p.LastName AS PatientName,
               d.FullName AS DoctorName, d.Specialisation, a.AppointmentStatus, a.Notes
        FROM Appointments a
        JOIN Patients p ON a.PatientNumber = p.PatientNumber
        JOIN Doctors d ON a.DoctorID = d.DoctorID
        ORDER BY a.AppointmentDate DESC, a.AppointmentTime DESC
        """,
        demo=[(a[0], a[1], a[2], a[4], a[5],
               DOCTOR_SPEC.get(a[5], "General Practitioner"), a[6], a[7])
              for a in demo_appointments()])

    return render_template("all_appointments.html", appointments=all_appointments)

# ======================================================================
# 2.5 Innovation Features
# ======================================================================


def get_patients():
    return fetch_rows(
        "SELECT PatientNumber, FirstName, LastName, DateOfBirth, Gender, "
        "ContactNumber, Email, ResidentialAddress FROM Patients "
        "ORDER BY RegistrationDate DESC, PatientNumber DESC",
        demo=DEMO_PATIENTS)


@app.route("/patient_portal")
def patient_portal():
    if "user" not in session:
        return redirect(url_for("login"))
    return render_template("patient_portal.html", patients=get_patients())


@app.route("/history/<patient_number>")
def patient_history(patient_number):
    if "user" not in session:
        return redirect(url_for("login"))

    patient = None
    for p in get_patients():
        if p[0] == patient_number:
            patient = p
            break
    if not patient:
        flash("No patient found with number %s." % patient_number, "error")
        return redirect(url_for("patient_portal"))

    history = fetch_rows(
        """
        SELECT a.AppointmentDate, a.AppointmentTime, d.FullName, a.AppointmentStatus, a.Notes
        FROM Appointments a
        JOIN Doctors d ON a.DoctorID = d.DoctorID
        WHERE a.PatientNumber = ?
        ORDER BY a.AppointmentDate DESC, a.AppointmentTime DESC
        """,
        params=(patient_number,),
        demo=demo_history(patient_number)[0],
    )

    allergies, conditions, byline, _ = demo_history(patient_number)

    return render_template("patient_history.html",
                           patient=patient, history=history,
                           allergies=allergies, conditions=conditions)


@app.route("/sms_reminders", methods=["GET", "POST"])
def sms_reminders():
    if "user" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":
        action = request.form.get("action")
        target = request.form.get("target")
        sent = set(session.get("sms_sent", []))
        if action == "send" and target:
            sent.add(target)
        elif action == "send_all":
            for item in session.get("sms_pending_reminders", []):
                sent.add(item)
        session["sms_sent"] = list(sent)

    # upcoming appointments in the next 7 days
    today = datetime.date.today()
    week_later = (today + datetime.timedelta(days=7)).strftime("%Y-%m-%d")
    rows = fetch_rows(
        """
        SELECT a.AppointmentNumber, a.AppointmentDate, a.AppointmentTime,
               p.FirstName + ' ' + p.LastName AS PatientName,
               p.ContactNumber, d.FullName AS DoctorName, a.AppointmentStatus
        FROM Appointments a
        JOIN Patients p ON a.PatientNumber = p.PatientNumber
        JOIN Doctors d ON a.DoctorID = d.DoctorID
        WHERE a.AppointmentDate BETWEEN ? AND ?
        ORDER BY a.AppointmentDate ASC, a.AppointmentTime ASC
        """,
        params=(today.strftime("%Y-%m-%d"), week_later),
        demo=[(a[0], a[1], a[2], a[4],
               PATIENT_LOOKUP.get(a[3], ("", "", "", "", "", "082 555 0101", "", ""))[5],
               a[5], a[6])
              for a in demo_appointments() if a[1] >= today.strftime("%Y-%m-%d")],
    )
    session["sms_pending_reminders"] = [str(r[0]) for r in rows]
    sent = set(session.get("sms_sent", []))

    reminders = []
    for r in rows:
        key = str(r[0])
        reminders.append({
            "number": key,
            "date": fmt_date(r[1]),
            "time": fmt_time(r[2]),
            "patient": r[3],
            "contact": r[4],
            "doctor": r[5],
            "status": r[6],
            "sent": key in sent,
        })

    sent_count = sum(1 for rem in reminders if rem["sent"])
    return render_template("sms_reminders.html", reminders=reminders,
                           sent_count=sent_count, total=len(reminders))


@app.route("/calendar")
def calendar():
    if "user" not in session:
        return redirect(url_for("login"))

    today = datetime.date.today()
    first = today.replace(day=1)
    last = (first + datetime.timedelta(days=32)).replace(day=1) - datetime.timedelta(days=1)

    rows = fetch_rows(
        """
        SELECT a.AppointmentNumber, a.AppointmentDate, a.AppointmentTime,
               p.FirstName + ' ' + p.LastName AS PatientName,
               d.FullName AS DoctorName, a.AppointmentStatus
        FROM Appointments a
        JOIN Patients p ON a.PatientNumber = p.PatientNumber
        JOIN Doctors d ON a.DoctorID = d.DoctorID
        WHERE a.AppointmentDate BETWEEN ? AND ?
        ORDER BY a.AppointmentDate ASC, a.AppointmentTime ASC
        """,
        params=(first.strftime("%Y-%m-%d"), last.strftime("%Y-%m-%d")),
        demo=[(a[0], a[1], a[2], a[4], a[5], a[6])
              for a in demo_appointments()
              if first.strftime("%Y-%m-%d") <= a[1] <= last.strftime("%Y-%m-%d")],
    )

    month_events = {}
    for r in rows:
        day = fmt_date(r[1])
        month_events.setdefault(day, []).append({
            "number": r[0], "time": fmt_time(r[2]),
            "patient": r[3], "doctor": r[4], "status": r[5],
        })

    return render_template("calendar.html",
                           month_year=first.strftime("%B %Y"),
                           month_events=month_events,
                           today=today.strftime("%Y-%m-%d"),
                           year=first.year,
                           month_num=first.month,
                           weekday_offset=(first.weekday() + 1) % 7,
                           days_in_month=last.day)


@app.route("/reports")
def reports():
    if "user" not in session:
        return redirect(url_for("login"))

    conn = get_connection()
    data = None
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT d.Specialisation, COUNT(*)
                FROM Appointments a JOIN Doctors d ON a.DoctorID = d.DoctorID
                GROUP BY d.Specialisation ORDER BY COUNT(*) DESC
            """)
            by_spec = cursor.fetchall()
            cursor.execute("""
                SELECT AppointmentStatus, COUNT(*)
                FROM Appointments GROUP BY AppointmentStatus ORDER BY COUNT(*) DESC
            """)
            by_status = cursor.fetchall()
            cursor.execute("""
                SELECT Gender, COUNT(*) FROM Patients GROUP BY Gender
            """)
            by_gender = cursor.fetchall()
            cursor.execute("""
                SELECT CAST(a.AppointmentDate AS DATE) AS d, COUNT(*)
                FROM Appointments a
                WHERE a.AppointmentDate >= DATEADD(day, -6, CAST(GETDATE() AS DATE))
                GROUP BY CAST(a.AppointmentDate AS DATE)
                ORDER BY d ASC
            """)
            by_day = cursor.fetchall()
            data = {
                "by_spec": by_spec, "by_status": by_status,
                "by_gender": by_gender, "by_day": by_day,
            }
        except Exception as e:
            print("Reports query error:", e)
        finally:
            try:
                conn.close()
            except Exception:
                pass

    if data is None:
        demo = demo_reports()
        today = datetime.date.today()
        data = {
            "by_spec": demo["by_specialisation"],
            "by_status": demo["by_status"],
            "by_gender": demo["by_gender"],
            "by_day": [(today - datetime.timedelta(days=6 - i), 6) for i in range(7)],
        }

    # normalise dates to strings (live queries may return datetime.date objects)
    data = dict(data)
    data["by_day"] = [(fmt_date(d), count) for d, count in data["by_day"]]

    spec_total = sum(x[1] for x in data["by_spec"]) or 1
    day_max = max((x[1] for x in data["by_day"]), default=0) or 1

    return render_template("reports.html", data=data,
                           spec_total=spec_total, day_max=day_max)


def qr_grid(seed, size=15):
    """Generate a deterministic QR-style square grid from a seed string."""
    h = hashlib.md5(seed.encode()).hexdigest()
    bits = []
    for i in range(size * size):
        block = h[i % len(h)]
        bits.append((ord(block) + i * 7) % 10 < 5)
    # finder squares
    for fx, fy in ((0, 0), (0, size - 7), (size - 7, 0)):
        for r in range(7):
            for c in range(7):
                edge = r in (0, 6) or c in (0, 6)
                core = 2 <= r <= 4 and 2 <= c <= 4
                bits[(fy + r) * size + (fx + c)] = edge or core
    return bits


@app.route("/qr_checkin", methods=["GET", "POST"])
def qr_checkin():
    if "user" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":
        target = request.form.get("target")
        checked = set(session.get("checked_in", []))
        if target:
            checked.add(target) if target not in checked else checked.discard(target)
        session["checked_in"] = list(checked)

    today = datetime.date.today().strftime("%Y-%m-%d")
    rows = fetch_rows(
        """
        SELECT a.AppointmentNumber, a.AppointmentDate, a.AppointmentTime,
               p.FirstName + ' ' + p.LastName AS PatientName,
               p.ContactNumber, d.FullName AS DoctorName, a.AppointmentStatus
        FROM Appointments a
        JOIN Patients p ON a.PatientNumber = p.PatientNumber
        JOIN Doctors d ON a.DoctorID = d.DoctorID
        WHERE a.AppointmentDate >= ?
        ORDER BY a.AppointmentDate ASC, a.AppointmentTime ASC
        """,
        params=(today,),
        demo=[(a[0], a[1], a[2], a[4],
               PATIENT_LOOKUP.get(a[3], ("", "", "", "", "", "082 555 0101", "", ""))[5],
               a[5], a[6])
              for a in demo_appointments()
              if a[1] >= today and a[6] != "Completed"],
    )

    checked = set(session.get("checked_in", []))
    items = []
    for r in rows:
        key = str(r[0])
        items.append({
            "number": key,
            "date": fmt_date(r[1]),
            "time": fmt_time(r[2]),
            "patient": r[3],
            "doctor": r[5],
            "status": "Checked In" if key in checked else r[6],
            "checked": key in checked,
            "qr": qr_grid("SC-" + key + "-" + r[3]),
            "qr_size": 16,
        })
    checked_count = sum(1 for it in items if it["checked"])
    return render_template("qr_checkin.html", items=items,
                           checked_count=checked_count)


@app.route("/assistant")
def assistant():
    if "user" not in session:
        return redirect(url_for("login"))
    return render_template("assistant.html")


@app.route("/innovations")
def innovations():
    return render_template("innovations.html")


if __name__ == "__main__":
    app.run(debug=True)