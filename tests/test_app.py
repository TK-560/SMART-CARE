"""Unit tests for the SmartCare application including the Section B
prototype features.

These tests mock the database layer (``app.get_connection``), so they run
without a live SQL Server connection. When the connection returns ``None``
the prototype routes fall back to their demo data, which is exactly what the
tests verify here.
"""
import datetime

import pytest
from werkzeug.security import generate_password_hash

import app as app_module

PASSWORD_HASH = generate_password_hash("pass123")
VALID_USER = (1, "Admin Rea", PASSWORD_HASH)

AUTH_ROUTES = ["/dashboard", "/register", "/book_appointment", "/appointments"]
PROTOTYPE_ROUTES = ["/patient_portal", "/sms_reminders", "/calendar",
                    "/reports", "/qr_checkin", "/assistant", "/booking_success"]


class FakeCursor:
    """Minimal stand-in for a pyodbc cursor."""

    def __init__(self, fetchone_result=None, fetchall_result=None):
        self.fetchone_result = fetchone_result
        self.fetchall_result = fetchall_result
        self.executed = []

    def execute(self, sql, params=None):
        self.executed.append((sql, params))

    def fetchone(self):
        return self.fetchone_result

    def fetchall(self):
        return self.fetchall_result

    def commit(self):
        pass

    def close(self):
        pass


class FakeConnection:
    """Minimal stand-in for a pyodbc connection."""

    def __init__(self, cursor):
        self._cursor = cursor

    def cursor(self):
        return self._cursor

    def commit(self):
        pass

    def close(self):
        pass


def make_conn(cursor):
    return FakeConnection(cursor)


@pytest.fixture
def client(monkeypatch):
    app_module.app.config.update(TESTING=True)
    monkeypatch.setattr(app_module, "get_connection", lambda: None)
    return app_module.app.test_client()


def login(client, username="admin", password="pass123", remember="1"):
    return client.post("/login", data={
        "username": username,
        "password": password,
        "remember": remember,
    })


# --- Public pages ------------------------------------------------------


def test_index_loads(client):
    assert client.get("/").status_code == 200


def test_login_page_loads(client):
    resp = client.get("/login")
    body = resp.get_data(as_text=True)
    assert resp.status_code == 200
    assert "Forgot password?" in body
    assert "Remember Me" in body
    assert "togglePassword" in body


def test_signup_page_loads(client):
    resp = client.get("/signup")
    assert resp.status_code == 200


def test_forgot_password_page_loads(client):
    resp = client.get("/forgot_password")
    body = resp.get_data(as_text=True)
    assert resp.status_code == 200
    assert "Forgot Password" in body
    assert "email" in body


def test_innovations_page_loads(client):
    resp = client.get("/innovations")
    body = resp.get_data(as_text=True)
    assert resp.status_code == 200
    assert "UX gain" in body
    assert "Patient Portal" in body


# --- Authentication guards --------------------------------------------


def test_register_redirects_when_logged_out(client):
    resp = client.post("/register")
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/login")


@pytest.mark.parametrize("route", AUTH_ROUTES + PROTOTYPE_ROUTES)
def test_protected_routes_redirect_when_logged_out(client, route):
    resp = client.get(route)
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/login")


# --- Login logic -------------------------------------------------------


def test_login_success_sets_session_and_remember_cookie(monkeypatch, client):
    class FakeCursor:
        def __init__(self):
            self.result = (1, "admin",
                           generate_password_hash("pass123", method="scrypt"))

        def execute(self, *args):
            return None

        def fetchone(self):
            return self.result

    class FakeConnection:
        def cursor(self):
            return FakeCursor()

        def close(self):
            return None

    monkeypatch.setattr(app_module, "get_connection", lambda: FakeConnection())

    resp = login(client)
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/dashboard")
    with client.session_transaction() as sess:
        assert sess.get("user") == "admin"
    assert "smartcare_username=admin" in resp.headers.get("Set-Cookie", "")


def test_login_wrong_password_shows_error(client, monkeypatch):
    cursor = FakeCursor(fetchone_result=VALID_USER)
    monkeypatch.setattr(app_module, "get_connection",
                        lambda: make_conn(cursor))
    resp = client.post("/login", data={
        "username": "Admin Rea", "password": "wrong"})
    assert resp.status_code == 200
    assert "Invalid username or password." in resp.get_data(as_text=True)


def test_login_unknown_user_shows_error(client, monkeypatch):
    cursor = FakeCursor(fetchone_result=None)
    monkeypatch.setattr(app_module, "get_connection",
                        lambda: make_conn(cursor))
    resp = client.post("/login", data={
        "username": "ghost", "password": "pass123"})
    assert resp.status_code == 200
    assert "Invalid username or password." in resp.get_data(as_text=True)


def test_login_missing_username_field_does_not_crash(client):
    resp = client.post("/login", data={"password": "pass123"})
    assert resp.status_code == 200


# --- Password hashing logic -------------------------------------------


def test_password_hash_round_trip():
    from werkzeug.security import check_password_hash
    hashed = generate_password_hash("s3cret")
    assert hashed.startswith("scrypt:")
    assert check_password_hash(hashed, "s3cret")
    assert not check_password_hash(hashed, "nope")


# --- Signup logic ------------------------------------------------------


def test_signup_password_mismatch(client):
    resp = client.post("/signup", data={
        "username": "newuser", "password": "pass12",
        "confirm_password": "pass34"})
    assert resp.status_code == 200
    assert "Passwords do not match." in resp.get_data(as_text=True)


def test_signup_duplicate_username_blocked(client, monkeypatch):
    cursor = FakeCursor(fetchone_result=(2, "Taken", "hash"))
    monkeypatch.setattr(app_module, "get_connection",
                        lambda: make_conn(cursor))
    resp = client.post("/signup", data={
        "username": "Taken", "password": "pass123",
        "confirm_password": "pass123"})
    assert resp.status_code == 200  # stays on signup, no redirect
    inserts = [sql for sql, _ in cursor.executed if "INSERT INTO Users" in sql]
    assert inserts == []  # duplicate was rejected before inserting


def test_signup_duplicate_shows_error_message(client, monkeypatch):
    cursor = FakeCursor(fetchone_result=(2, "Taken", "hash"))
    monkeypatch.setattr(app_module, "get_connection",
                        lambda: make_conn(cursor))
    resp = client.post("/signup", data={
        "username": "Taken", "password": "pass123",
        "confirm_password": "pass123"})
    assert resp.status_code == 200
    assert "That username is already taken." in resp.get_data(as_text=True)


def test_signup_success_redirects_to_login(client, monkeypatch):
    cursor = FakeCursor(fetchone_result=None)
    monkeypatch.setattr(app_module, "get_connection",
                        lambda: make_conn(cursor))
    resp = client.post("/signup", data={
        "username": "newuser", "password": "pass123",
        "confirm_password": "pass123"})
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/login")
    samt = [sql for sql, _ in cursor.executed if "INSERT INTO Users" in sql]
    assert len(samt) == 1


# --- Logout -----------------------------------------------------------


def test_logout_clears_session(client):
    with client.session_transaction() as sess:
        sess["user"] = "Admin Rea"
    resp = client.get("/logout")
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/login")
    with client.session_transaction() as sess:
        assert "user" not in sess


# --- Register patient -------------------------------------------------


def test_register_patient_insert(client, monkeypatch):
    cursor = FakeCursor()
    monkeypatch.setattr(app_module, "get_connection",
                        lambda: make_conn(cursor))
    with client.session_transaction() as sess:
        sess["user"] = "Admin Rea"
    today = datetime.date.today().strftime("%Y-%m-%d")
    resp = client.post("/register", data={
        "patient_number": "90000001",
        "sa_id": "9001015800081",
        "first_name": "Test", "last_name": "Patient",
        "dob": "1990-01-01", "gender": "Male",
        "contact_number": "0820000001",
        "email": "test@example.com",
        "residential_address": "1 Test St",
        "emergency_contact": "Guardian",
    })
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/dashboard")
    inserts = [(sql, p) for sql, p in cursor.executed
               if "INSERT INTO Patients" in sql]
    assert len(inserts) == 1
    params = inserts[0][1]
    assert params[0] == "90000001"
    assert params[10] == today  # RegistrationDate


# --- Book appointment -------------------------------------------------


def test_book_appointment_insert(client, monkeypatch):
    cursor = FakeCursor()
    monkeypatch.setattr(app_module, "get_connection",
                        lambda: make_conn(cursor))
    with client.session_transaction() as sess:
        sess["user"] = "Admin Rea"
    resp = client.post("/book_appointment", data={
        "patient_id": "90000001",
        "doctor_id": "1",
        "appointment_date": "2026-12-01",
        "appointment_time": "09:00",
        "notes": "Follow-up",
    })
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/booking_success")
    inserts = [(sql, p) for sql, p in cursor.executed
               if "INSERT INTO Appointments" in sql]
    assert len(inserts) == 1
    assert inserts[0][1] == (
        "2026-12-01", "09:00", "1", "90000001", "Confirmed", "Follow-up")


# --- Dashboard --------------------------------------------------------


def test_dashboard_renders_metrics(client, monkeypatch):
    cursor = FakeCursor(fetchone_result=(7,), fetchall_result=[])
    monkeypatch.setattr(app_module, "get_connection",
                        lambda: make_conn(cursor))
    with client.session_transaction() as sess:
        sess["user"] = "Admin Rea"
    resp = client.get("/dashboard")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "Overview" in body
    assert "7" in body


def test_dashboard_shows_upcoming_appointments(client, monkeypatch):
    row = ("1", "2026-09-10", "08:00", "Thabo Mokoena",
           "Dr Sarah Smith", "Confirmed")
    cursor = FakeCursor(fetchone_result=(7,), fetchall_result=[row])
    monkeypatch.setattr(app_module, "get_connection",
                        lambda: make_conn(cursor))
    with client.session_transaction() as sess:
        sess["user"] = "Admin Rea"
    resp = client.get("/dashboard")
    assert resp.status_code == 200
    assert "Dr Sarah Smith" in resp.get_data(as_text=True)


def test_dashboard_has_quick_actions_and_notifications(client):
    with client.session_transaction() as sess:
        sess["user"] = "admin"
    resp = client.get("/dashboard")
    body = resp.get_data(as_text=True)
    assert resp.status_code == 200
    assert "Total Patients" in body
    assert "Total Doctors" in body
    assert "Quick Actions" in body
    assert "Notifications" in body


# --- All appointments -------------------------------------------------


def test_all_appointments_lists_records(client, monkeypatch):
    row = ("1", "2026-09-10", "08:00", "Thabo Mokoena", "Dr Sarah Smith",
           "General Practitioner", "Confirmed", "Follow-up")
    cursor = FakeCursor(fetchall_result=[row])
    monkeypatch.setattr(app_module, "get_connection",
                        lambda: make_conn(cursor))
    with client.session_transaction() as sess:
        sess["user"] = "Admin Rea"
    resp = client.get("/appointments")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "Dr Sarah Smith" in body
    assert "Follow-up" in body


# --- Section B prototype pages ----------------------------------------


def test_register_page_has_inline_validation(client):
    with client.session_transaction() as sess:
        sess["user"] = "admin"
    body = client.get("/register").get_data(as_text=True)
    assert "stepper" in body
    assert "field-hint" in body
    assert "Patient number must be exactly 8 digits" in body


def test_booking_page_has_calendar_doctor_cards_and_status(client):
    with client.session_transaction() as sess:
        sess["user"] = "admin"
    body = client.get("/book_appointment").get_data(as_text=True)
    assert "doctor-card" in body
    assert "calendar-widget" in body
    assert "time-slot" in body
    assert "status-confirmed" in body


def test_patient_portal_lists_patients(client):
    with client.session_transaction() as sess:
        sess["user"] = "admin"
    resp = client.get("/patient_portal")
    body = resp.get_data(as_text=True)
    assert resp.status_code == 200
    assert "Patient Portal" in body
    assert "History" in body


def test_medical_history_page_renders(client):
    with client.session_transaction() as sess:
        sess["user"] = "admin"
    resp = client.get("/history/90000125")
    body = resp.get_data(as_text=True)
    assert resp.status_code == 200
    assert "Medical History" in body
    assert "timeline" in body


def test_sms_reminders_page_renders(client):
    with client.session_transaction() as sess:
        sess["user"] = "admin"
    resp = client.get("/sms_reminders")
    body = resp.get_data(as_text=True)
    assert resp.status_code == 200
    assert "SMS" in body
    assert "Send SMS" in body or "Reminders Sent" in body


def test_calendar_page_renders(client):
    with client.session_transaction() as sess:
        sess["user"] = "admin"
    resp = client.get("/calendar")
    body = resp.get_data(as_text=True)
    assert resp.status_code == 200
    assert "Appointment Calendar" in body
    assert "monthGrid" in body or "calendar-grid" in body


def test_reports_page_renders(client):
    with client.session_transaction() as sess:
        sess["user"] = "admin"
    resp = client.get("/reports")
    body = resp.get_data(as_text=True)
    assert resp.status_code == 200
    assert "Reports" in body
    assert "bar-fill" in body


def test_qr_checkin_page_renders(client):
    with client.session_transaction() as sess:
        sess["user"] = "admin"
    resp = client.get("/qr_checkin")
    body = resp.get_data(as_text=True)
    assert resp.status_code == 200
    assert "QR" in body
    assert "svg" in body


def test_assistant_page_renders(client):
    with client.session_transaction() as sess:
        sess["user"] = "admin"
    resp = client.get("/assistant")
    body = resp.get_data(as_text=True)
    assert resp.status_code == 200
    assert "Smartie" in body


# --- Doctor management -------------------------------------------------


@pytest.mark.parametrize("url", [
    "/doctors", "/add_doctor",
])
def test_doctor_routes_redirect_when_logged_out(client, url):
    resp = client.get(url)
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/login")


def test_edit_doctor_redirects_when_logged_out(client):
    resp = client.get("/edit_doctor/1")
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/login")


def test_delete_doctor_redirects_when_logged_out(client):
    resp = client.post("/delete_doctor/1")
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/login")


def test_all_doctors_lists_records(client, monkeypatch):
    row = (1, "Dr Sarah Smith", "Cardiology", "0820000000", "sarah@smartcare.com")
    cursor = FakeCursor(fetchall_result=[row])
    monkeypatch.setattr(app_module, "get_connection",
                        lambda: make_conn(cursor))
    with client.session_transaction() as sess:
        sess["user"] = "Admin Rea"
    resp = client.get("/doctors")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "Dr Sarah Smith" in body
    assert "Cardiology" in body


def test_add_doctor_insert(client, monkeypatch):
    cursor = FakeCursor()
    monkeypatch.setattr(app_module, "get_connection",
                        lambda: make_conn(cursor))
    with client.session_transaction() as sess:
        sess["user"] = "Admin Rea"
    resp = client.post("/add_doctor", data={
        "full_name": "Dr John Doe",
        "specialisation": "Neurology",
        "phone_number": "0821234567",
        "email": "john@smartcare.com",
    })
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/doctors")
    inserts = [(sql, p) for sql, p in cursor.executed
               if "INSERT INTO Doctors" in sql]
    assert len(inserts) == 1
    assert inserts[0][1] == (
        "Dr John Doe", "Neurology", "0821234567", "john@smartcare.com")


def test_add_doctor_missing_fields_shows_error(client, monkeypatch):
    cursor = FakeCursor()
    monkeypatch.setattr(app_module, "get_connection",
                        lambda: make_conn(cursor))
    with client.session_transaction() as sess:
        sess["user"] = "Admin Rea"
    resp = client.post("/add_doctor", data={
        "full_name": "",
        "specialisation": "Neurology",
        "phone_number": "",
        "email": "",
    })
    assert resp.status_code == 200
    assert "required" in resp.get_data(as_text=True).lower()


def test_edit_doctor_update(client, monkeypatch):
    doctor = (1, "Dr Old Name", "Cardiology", "0820000000", "old@smartcare.com")
    cursor = FakeCursor(fetchone_result=doctor)
    monkeypatch.setattr(app_module, "get_connection",
                        lambda: make_conn(cursor))
    with client.session_transaction() as sess:
        sess["user"] = "Admin Rea"
    resp = client.post("/edit_doctor/1", data={
        "full_name": "Dr New Name",
        "specialisation": "Dermatology",
        "phone_number": "0829999999",
        "email": "new@smartcare.com",
    })
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/doctors")
    updates = [(sql, p) for sql, p in cursor.executed
               if "UPDATE Doctors" in sql]
    assert len(updates) == 1
    assert updates[0][1] == (
        "Dr New Name", "Dermatology", "0829999999", "new@smartcare.com", 1)


def test_edit_doctor_not_found_redirects(client, monkeypatch):
    cursor = FakeCursor(fetchone_result=None)
    monkeypatch.setattr(app_module, "get_connection",
                        lambda: make_conn(cursor))
    with client.session_transaction() as sess:
        sess["user"] = "Admin Rea"
    resp = client.get("/edit_doctor/999")
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/doctors")


def test_delete_doctor_removes_record(client, monkeypatch):
    cursor = FakeCursor()
    monkeypatch.setattr(app_module, "get_connection",
                        lambda: make_conn(cursor))
    with client.session_transaction() as sess:
        sess["user"] = "Admin Rea"
    resp = client.post("/delete_doctor/1")
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/doctors")
    deletes = [(sql, p) for sql, p in cursor.executed
               if "DELETE FROM Doctors" in sql]
    assert len(deletes) == 1
    assert deletes[0][1] == (1,)