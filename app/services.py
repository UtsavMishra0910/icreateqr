import io
import re
from pathlib import Path
from typing import Iterable
from zipfile import ZipFile, ZIP_DEFLATED

import pandas as pd
import qrcode
from sqlalchemy.orm import Session

from app.config import BASE_DIR, QR_DIR
from app.models import Student

EXPECTED_COLUMNS = ["name", "reg_no", "email"]
HEADER_ALIASES = {
    "name": "name",
    "student_name": "name",
    "full_name": "name",
    "reg_no": "reg_no",
    "regno": "reg_no",
    "registration_number": "reg_no",
    "registration_no": "reg_no",
    "registration": "reg_no",
    "email": "email",
    "email_address": "email",
    "mail": "email",
}


def _normalize_cell(value: object) -> str:
    # Treat empty spreadsheet values consistently before validation.
    if pd.isna(value):
        return ""
    text = str(value).strip()
    if text.lower() in {"", "nan", "none", "null", "na", "n/a"}:
        return ""
    return text


def _normalize_reg_no(value: object) -> str:
    text = _normalize_cell(value)
    # Excel often converts text-like numbers to float strings (e.g. 101.0).
    if re.fullmatch(r"\d+\.0", text):
        return text[:-2]
    return text


def normalize_columns(columns: Iterable[str]) -> list[str]:
    normalized = []
    for col in columns:
        safe = re.sub(r"\s+", "_", str(col).strip().lower())
        normalized.append(HEADER_ALIASES.get(safe, safe))
    return normalized


def read_students_dataframe(file_path: Path) -> pd.DataFrame:
    suffix = file_path.suffix.lower()
    if suffix == ".csv":
        df = pd.read_csv(file_path)
    elif suffix == ".xlsx":
        df = pd.read_excel(file_path)
    else:
        raise ValueError("Unsupported file format. Use .csv or .xlsx")

    df.columns = normalize_columns(df.columns)
    missing = [col for col in EXPECTED_COLUMNS if col not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {', '.join(missing)}")

    # Keep only expected columns and sanitize common formatting issues.
    clean_df = df[EXPECTED_COLUMNS].copy()
    clean_df["name"] = clean_df["name"].apply(_normalize_cell)
    clean_df["reg_no"] = clean_df["reg_no"].apply(_normalize_reg_no)
    clean_df["email"] = clean_df["email"].apply(_normalize_cell).str.lower()
    clean_df = clean_df[(clean_df["name"] != "") & (clean_df["reg_no"] != "") & (clean_df["email"] != "")]
    return clean_df.drop_duplicates(subset=["reg_no"])


def generate_qr(reg_no: str) -> str:
    # Keep QR payload simple and deterministic for reliable scanner parsing.
    payload = f"REG:{reg_no}"
    file_name = f"{reg_no}.png"
    full_path = QR_DIR / file_name

    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(payload)
    qr.make(fit=True)
    image = qr.make_image(fill_color="black", back_color="white")
    image.save(full_path)
    return str(Path("qrcodes") / file_name)


def upsert_students(df: pd.DataFrame, db: Session) -> tuple[int, int]:
    created = 0
    updated = 0

    for _, row in df.iterrows():
        existing = db.query(Student).filter(Student.reg_no == row["reg_no"]).first()
        qr_code_path = generate_qr(row["reg_no"])

        if existing:
            # Update allows re-uploading revised student details.
            existing.name = row["name"]
            existing.email = row["email"]
            existing.qr_code_path = qr_code_path
            updated += 1
        else:
            db.add(
                Student(
                    name=row["name"],
                    reg_no=row["reg_no"],
                    email=row["email"],
                    qr_code_path=qr_code_path,
                )
            )
            created += 1

    db.commit()
    return created, updated


def build_qr_zip(db: Session) -> bytes:
    students = db.query(Student).all()
    memory_file = io.BytesIO()

    with ZipFile(memory_file, "w", ZIP_DEFLATED) as zipf:
        for student in students:
            qr_path = Path(student.qr_code_path)
            full_path = BASE_DIR / qr_path
            if not full_path.exists():
                generate_qr(student.reg_no)
            if full_path.exists():
                zipf.write(full_path, arcname=f"{student.reg_no}.png")

    memory_file.seek(0)
    return memory_file.getvalue()
