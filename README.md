# QR Attendance Web Application (FastAPI + PostgreSQL)

Production-ready web app for student onboarding via Excel/CSV, QR generation, live attendance scanning, and attendance reporting.

## Folder Structure

```text
icreateqr/
├── app/
│   ├── __init__.py
│   ├── config.py
│   ├── database.py
│   ├── main.py
│   ├── models.py
│   ├── schemas.py
│   └── services.py
├── static/
│   ├── app.js
│   ├── scanner.js
│   └── style.css
├── templates/
│   ├── base.html
│   ├── index.html
│   ├── reports.html
│   ├── scanner.html
│   └── students.html
├── .env.example
├── .gitignore
├── render.yaml
├── requirements.txt
└── README.md
```

## Features

- Upload `.xlsx` or `.csv` with `name`, `reg_no`, `email`
- Auto-generate unique QR code per `reg_no`
- Student list with QR preview
- Download all QR images as one ZIP
- Live webcam scanner (HTML5 QR scanner)
- Attendance mark with timestamp
- Duplicate prevention (`1 student per day`)
- Attendance report view
- Validation and error handling for common failures

## Database Schema

### `students`
- `id`
- `name`
- `reg_no` (unique)
- `email` (unique)
- `qr_code_path`
- `created_at`

### `attendance`
- `id`
- `student_id` (FK -> students.id)
- `scan_time`
- `date`
- unique constraint on (`student_id`, `date`)

## Local Setup

1. Create virtual environment and install dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

2. Create PostgreSQL database:

```sql
CREATE DATABASE qr_attendance;
```

3. Copy env file:

```powershell
Copy-Item .env.example .env
```

4. Update `.env`:

```env
DATABASE_URL=postgresql+psycopg2://postgres:postgres@localhost:5432/qr_attendance
SECRET_KEY=strong-random-secret
UPLOAD_DIR=uploads
QR_DIR=qrcodes
```

5. Run the application:

```powershell
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Open: `http://localhost:8000`

## Upload File Format

Example CSV:

```csv
name,reg_no,email
Alice Johnson,REG001,alice@example.com
Bob Smith,REG002,bob@example.com
```

## Production Readiness Notes

- Uses connection pool pre-ping for DB reliability.
- Handles bad file types, missing columns, empty uploads, and duplicates.
- Uses SQL unique constraints for attendance duplicate prevention.
- QR files are auto-regenerated if missing (useful on ephemeral disks).
- Run with Gunicorn + Uvicorn workers for concurrency:

```bash
gunicorn -w 3 -k uvicorn.workers.UvicornWorker app.main:app
```

For 100 concurrent users, scale by worker count and use a managed PostgreSQL instance.

## Deploy on Render (Free)

### Option A: One-click with `render.yaml`
1. Push this repo to GitHub.
2. In Render: `New` -> `Blueprint` -> select your repo.
3. Render auto-creates:
   - Web service (`qr-attendance-app`)
   - PostgreSQL (`qr-attendance-db`)
4. Deploy and open app URL.

### Option B: Manual
1. Create `Web Service` (Python) from GitHub repo.
2. Build command:
   - `pip install -r requirements.txt`
3. Start command:
   - `gunicorn -w 3 -k uvicorn.workers.UvicornWorker app.main:app`
4. Create Render PostgreSQL instance.
5. Add env vars in web service:
   - `DATABASE_URL` = Render DB connection string
   - `SECRET_KEY` = strong random value
   - `UPLOAD_DIR` = `uploads`
   - `QR_DIR` = `qrcodes`
6. Redeploy.

## Railway / PythonAnywhere (Alternative)

- Railway:
  - Create PostgreSQL plugin and Python service.
  - Set same env vars and same start command.
- PythonAnywhere:
  - Use a web app + PostgreSQL add-on.
  - Configure WSGI/ASGI with Gunicorn and env vars.

## Testing Instructions

1. Upload CSV/XLSX with valid columns.
2. Confirm students appear in `/students`.
3. Open each QR and verify unique QR per `reg_no`.
4. Download ZIP from `/qrcodes/download`.
5. Open `/scanner` and scan QR:
   - first scan: success
   - same day second scan: duplicate message
6. Check `/reports` for timestamped logs.
7. Restart server and verify QR link still works (auto-regeneration).

## API/Routes

- `GET /` dashboard
- `GET /students` student list/upload page
- `POST /students/upload` upload Excel/CSV
- `GET /students/{reg_no}/qr` view student QR
- `GET /qrcodes/download` download ZIP of all QR
- `GET /scanner` live scanner UI
- `POST /attendance/mark` mark attendance from scanner
- `GET /reports` attendance reports
