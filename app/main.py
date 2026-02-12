from datetime import date, datetime
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, StreamingResponse
from starlette.middleware.sessions import SessionMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import BASE_DIR, SECRET_KEY, UPLOAD_DIR
from app.database import Base, engine, get_db
from app.models import Attendance, Student
from app.services import build_qr_zip, generate_qr, read_students_dataframe, upsert_students

app = FastAPI(title="QR Attendance System", version="1.0.0")
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
app.mount("/qrcodes", StaticFiles(directory=str(BASE_DIR / "qrcodes")), name="qrcodes")

ADMIN_EMAIL = "utsav.24bai10564@vitbhopal.ac.in"
ADMIN_PASSWORD = "icreateqr"


@app.on_event("startup")
def startup():
    # Auto-create tables for simple deployments without a migration tool.
    Base.metadata.create_all(bind=engine)


@app.get("/", response_class=HTMLResponse)
def home(request: Request, db: Session = Depends(get_db)):
    student_count = db.query(Student).count()
    today_attendance = db.query(Attendance).filter(Attendance.date == date.today()).count()
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "student_count": student_count,
            "today_attendance": today_attendance,
        },
    )


@app.get("/students", response_class=HTMLResponse)
def students_page(request: Request, db: Session = Depends(get_db)):
    students = db.query(Student).order_by(Student.created_at.desc()).all()
    return templates.TemplateResponse("students.html", {"request": request, "students": students})


@app.post("/students/upload")
async def upload_students(request: Request, file: UploadFile = File(...), db: Session = Depends(get_db)):
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in {".xlsx", ".csv"}:
        raise HTTPException(status_code=400, detail="Only .xlsx and .csv are allowed")

    # Save upload to disk first so pandas can read both CSV and XLSX safely.
    temp_path = UPLOAD_DIR / f"{datetime.utcnow().timestamp()}_{file.filename}"
    content = await file.read()
    temp_path.write_bytes(content)

    try:
        df = read_students_dataframe(temp_path)
        if df.empty:
            raise HTTPException(status_code=400, detail="No valid student rows found in file")
        created, updated = upsert_students(df, db)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail="Duplicate registration number or email in dataset") from exc
    finally:
        if temp_path.exists():
            temp_path.unlink()

    response = RedirectResponse(url="/students", status_code=303)
    response.set_cookie("flash", f"Upload complete: {created} created, {updated} updated", max_age=5)
    return response


@app.get("/qrcodes/download")
def download_qr_zip(db: Session = Depends(get_db)):
    zip_bytes = build_qr_zip(db)
    return StreamingResponse(
        iter([zip_bytes]),
        media_type="application/x-zip-compressed",
        headers={"Content-Disposition": "attachment; filename=student_qrcodes.zip"},
    )


@app.get("/students/{reg_no}/qr")
def student_qr(reg_no: str, db: Session = Depends(get_db)):
    student = db.query(Student).filter(Student.reg_no == reg_no).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    full_path = BASE_DIR / student.qr_code_path
    if not full_path.exists():
        student.qr_code_path = generate_qr(student.reg_no)
        db.commit()
        full_path = BASE_DIR / student.qr_code_path

    return FileResponse(path=full_path, media_type="image/png", filename=f"{reg_no}.png")


@app.get("/scanner", response_class=HTMLResponse)
def scanner_page(request: Request):
    return templates.TemplateResponse("scanner.html", {"request": request})


@app.post("/attendance/mark")
def mark_attendance(reg_no: str = Form(...), db: Session = Depends(get_db)):
    student = db.query(Student).filter(Student.reg_no == reg_no.strip()).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    today = date.today()
    # Prevent duplicate attendance for the same day.
    existing = (
        db.query(Attendance)
        .filter(Attendance.student_id == student.id, Attendance.date == today)
        .first()
    )
    if existing:
        return {"status": "duplicate", "message": f"{student.name} already marked today"}

    record = Attendance(student_id=student.id, scan_time=datetime.utcnow(), date=today)
    db.add(record)
    db.commit()
    return {
        "status": "success",
        "message": f"Attendance marked for {student.name}",
        "student": student.name,
        "reg_no": student.reg_no,
        "time": record.scan_time.isoformat(),
    }


@app.get("/reports", response_class=HTMLResponse)
def reports_page(request: Request, db: Session = Depends(get_db)):
    rows = (
        db.query(Attendance, Student)
        .join(Student, Attendance.student_id == Student.id)
        .order_by(Attendance.scan_time.desc())
        .all()
    )
    return templates.TemplateResponse("reports.html", {"request": request, "rows": rows})


@app.get("/admin", response_class=HTMLResponse)
def admin_page(request: Request):
    is_admin = bool(request.session.get("is_admin"))
    return templates.TemplateResponse("admin.html", {"request": request, "is_admin": is_admin})


@app.post("/admin/login")
def admin_login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
):
    if email.strip().lower() != ADMIN_EMAIL or password != ADMIN_PASSWORD:
        response = RedirectResponse(url="/admin", status_code=303)
        response.set_cookie("flash", "Invalid admin email or password", max_age=5)
        return response

    request.session["is_admin"] = True
    request.session["admin_email"] = ADMIN_EMAIL
    response = RedirectResponse(url="/admin", status_code=303)
    response.set_cookie("flash", "Admin login successful", max_age=5)
    return response


@app.post("/admin/logout")
def admin_logout(request: Request):
    request.session.clear()
    response = RedirectResponse(url="/admin", status_code=303)
    response.set_cookie("flash", "Admin logged out", max_age=5)
    return response


@app.post("/admin/delete")
def admin_delete_data(request: Request, scope: str = Form(...), db: Session = Depends(get_db)):
    if not request.session.get("is_admin"):
        raise HTTPException(status_code=403, detail="Admin login required")

    if scope == "attendance":
        db.query(Attendance).delete()
        db.commit()
        response = RedirectResponse(url="/admin", status_code=303)
        response.set_cookie("flash", "Attendance records deleted", max_age=5)
        return response

    if scope == "all":
        db.query(Attendance).delete()
        db.query(Student).delete()
        db.commit()
        response = RedirectResponse(url="/admin", status_code=303)
        response.set_cookie("flash", "Students and attendance deleted", max_age=5)
        return response

    raise HTTPException(status_code=400, detail="Invalid delete scope")
