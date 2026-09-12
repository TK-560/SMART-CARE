# SMART-CARE

A web-based healthcare management system for a doctors practice. Staff can register patients and book appointments over the internet, and get a live overview of what's happening at the clinic.

## Purpose

SMART-CARE lets clinic staff replace paper-based patient intake and appointment books with a single web app:

- **Register patients** with their personal, contact, and emergency details
- **Book appointments** by choosing a patient, a doctor, and a date/time slot
- **Dashboard** showing total patients, doctors, appointments, today's schedule, and upcoming appointments
- **View all appointments** with a live search/filter
- **Staff accounts** with secure signup and login

## Technologies Used

| Layer       | Technology                                   |
|-------------|----------------------------------------------|
| Backend     | Python, Flask                                |
| Database    | Microsoft SQL Server (via pyodbc / ODBC 17)  |
| Auth        | Werkzeug password hashing (scrypt)           |
| Frontend    | HTML, Jinja2 templates, CSS, vanilla JavaScript |
| Tooling     | Git, pip, virtual environment (`.venv/`)     |

See `requirements.txt` for the pinned dependency versions.

## Getting Started

1. Create the SQL Server database using `schema.sql` (or `PM12,SQL/Create_table.sql`).
2. Seed reference data with the scripts in `PM12,SQL/`.
3. Install dependencies: `pip install -r requirements.txt`
4. Adjust the connection string in `database.py` for your SQL Server instance.
5. Run: `python app.py`

## Future Plans

- Server-side input validation and length checks (not just client-side)
- Prevent double-booking with unique doctor/date/time constraints
- CSRF protection and stronger session security
- Medical aid details on the patient registration form
- Appointment status management (confirm/cancel/complete)
- Reports and analytics for the practice
- Deployment-ready configuration (env-based secrets, no debug mode)

## Prototype Features (Section B)

The `prototype-features` branch demonstrates the improved SmartCare prototype.
Every screen falls back to representative demo data when the SQL Server database
is unreachable, so the design can be presented anywhere.

### 2.1 Login page
- Modern split layout with password **visibility toggle**, **Forgot Password**
  flow (`/forgot_password`), and **Remember Me** (30-day cookie that pre-fills
  the username).

### 2.2 Patient registration
- Grouped sections, a 3-step stepper, and **inline per-field validation
  messages** with smooth scroll-to-first-error.

### 2.3 Appointment booking
- **Doctor cards**, an interactive **month calendar** with past-date blocking,
  **quick-select time slots**, a live booking summary, and a confirmation page
  showing **appointment status** (`/booking_success`).

### 2.4 Dashboard
- Metrics for Total Patients / Total Doctors / Today's / All-time
  appointments, **Quick Actions** for every routine task, and a
  **Notifications** panel generated from live counts.

### 2.5 Innovation features
| Feature | Route | UX improvement |
|---|---|---|
| Patient Portal | `/patient_portal` | One search point for every patient record |
| SMS Reminders | `/sms_reminders` | One-tap texts, fewer no-shows |
| Appointment Calendar | `/calendar` | Month grid with per-day schedules |
| Reports Dashboard | `/reports` | CSV-free practice analytics |
| AI Chat Assistant | `/assistant` | Scripted answers for new staff |
| QR Code Check-in | `/qr_checkin` | Zero-queue arrivals |
| Medical History | `/history/<patient>` | Visit timeline, allergies, conditions |
| Innovation hub | `/innovations` | Explains each feature's UX benefit |

The prototype is covered by unit tests in `tests/test_app.py` (DB-independent,
run with `python -m pytest tests/test_app.py -v`).