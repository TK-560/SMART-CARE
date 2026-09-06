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