"""Unit tests for the SmartCare application including the Section B
prototype features.

These tests mock the database layer (``app.get_connection``), so they run
without a live SQL Server connection. When the connection returns ``None``
the prototype routes fall back to their demo data, which is exactly what the
tests verify here.
"""
import pytest
from werkzeug.security import generate_password_hash

import app as app_module

AUTH_ROUTES = ["/dashboard", "/register", "/book_appointment", "/appointments"]
PROTOTYPE_ROUTES = ["/patient_portal", "/sms_reminders", "/calendar",
                    "/reports", "/qr_checkin", "/assistant", "/booking_success"]


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


# ---- Public pages ------------------------------------------------------


def test_index_loads(client):
    resp = client.get("/")
    assert resp.status_code == 200


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


# ---- Auth behaviour ----------------------------------------------------


@pytest.mark.parametrize("route", AUTH_ROUTES + PROTOTYPE_ROUTES)
def test_protected_routes_redirect_when_logged_out(client, route):
    resp = client.get(route)
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/login")


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


def test_login_wrong_password_shows_error(monkeypatch, client):
    class FakeCursor:
        def execute(self, *args):
            return None

        def fetchone(self):
            return (1, "admin", generate_password_hash("nomatch"))

    class FakeConnection:
        def cursor(self):
            return FakeCursor()

        def close(self):
            return None

    monkeypatch.setattr(app_module, "get_connection", lambda: FakeConnection())

    resp = client.post("/login", data={"username": "admin",
                                       "password": "pass123"})
    assert resp.status_code == 200
    assert "Invalid username or password." in resp.get_data(as_text=True)


def test_login_unknown_user_shows_error(monkeypatch, client):
    class FakeCursor:
        def execute(self, *args):
            return None

        def fetchone(self):
            return None

    class FakeConnection:
        def cursor(self):
            return FakeCursor()

        def close(self):
            return None

    monkeypatch.setattr(app_module, "get_connection", lambda: FakeConnection())
    resp = client.post("/login", data={"username": "ghost",
                                       "password": "x"})
    assert resp.status_code == 200
    assert "Invalid username or password." in resp.get_data(as_text=True)


def test_login_missing_username_field_does_not_crash(client):
    resp = client.post("/login", data={"password": "pass123"})
    assert resp.status_code == 200


def test_signup_password_mismatch(client):
    resp = client.post("/signup", data={
        "username": "newstaff",
        "password": "abcd",
        "confirm_password": "abce",
    })
    assert resp.status_code == 200
    assert "Passwords do not match." in resp.get_data(as_text=True)


def test_logout_clears_session(client):
    with client.session_transaction() as sess:
        sess["user"] = "admin"
    resp = client.get("/logout")
    assert resp.status_code == 302
    with client.session_transaction() as sess:
        assert "user" not in sess


# ---- Section B prototype pages ----------------------------------------


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