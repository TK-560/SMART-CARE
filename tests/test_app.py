"""Unit tests for the SmartCare Flask application.

The database connection is mocked out (unittest.mock) so these tests run
without touching the live SQL Server database.
"""
import datetime

import pytest
from werkzeug.security import generate_password_hash

import app as app_module

PASSWORD_HASH = generate_password_hash("pass123")
VALID_USER = (1, "Admin Rea", PASSWORD_HASH)


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
    def fake_get_connection():
        return None

    monkeypatch.setattr(app_module, "get_connection", fake_get_connection)
    return app_module.app.test_client()


# --- Page availability -----------------------------------------------


def test_index_loads(client):
    assert client.get("/").status_code == 200


def test_login_page_loads(client):
    assert client.get("/login").status_code == 200


def test_signup_page_loads(client):
    assert client.get("/signup").status_code == 200


# --- Authentication guards -------------------------------------------


@pytest.mark.parametrize("url", [
    "/dashboard", "/register", "/book_appointment", "/appointments",
])
def test_protected_routes_redirect_when_logged_out(client, url):
    resp = client.get(url)
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/login")


def test_register_redirects_when_logged_out(client):
    resp = client.post("/register")
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/login")


# --- Login logic ------------------------------------------------------


def test_login_success_sets_session(client, monkeypatch):
    cursor = FakeCursor(fetchone_result=VALID_USER)
    monkeypatch.setattr(app_module, "get_connection",
                        lambda: make_conn(cursor))
    resp = client.post("/login", data={
        "username": "Admin Rea", "password": "pass123"})
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/dashboard")
    with client.session_transaction() as sess:
        assert sess.get("user") == "Admin Rea"


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


# --- Password hashing logic -------------------------------------------


def test_password_hash_round_trip():
    from werkzeug.security import check_password_hash
    hashed = generate_password_hash("s3cret")
    assert hashed.startswith("scrypt:")
    assert check_password_hash(hashed, "s3cret")
    assert not check_password_hash(hashed, "nope")


# --- Signup logic -----------------------------------------------------


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


@pytest.mark.xfail(
    reason="Bug: signup.html has no flash-message block, so the "
           "'That username is already taken.' message is never shown "
           "to the user. Fix recommended in maintenance.")
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
    assert resp.headers["Location"].endswith("/dashboard")
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


# --- Known bugs (documented, fix recommended) -------------------------


@pytest.mark.xfail(
    reason="Known bug: login crashes with AttributeError when the "
           "username field is omitted because .strip() is called on None. "
           "Fix recommended in maintenance.")
def test_login_missing_username_field_crashes(client):
    resp = client.post("/login", data={"password": "pass123"})
    assert resp.status_code == 200


# --- Doctor management --------------------------------------------------


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