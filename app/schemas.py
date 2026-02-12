from datetime import datetime, date

from pydantic import BaseModel, EmailStr


class StudentCreate(BaseModel):
    name: str
    reg_no: str
    email: EmailStr


class StudentRead(BaseModel):
    id: int
    name: str
    reg_no: str
    email: EmailStr
    qr_code_path: str
    created_at: datetime

    class Config:
        from_attributes = True


class AttendanceRead(BaseModel):
    id: int
    student_id: int
    scan_time: datetime
    date: date

    class Config:
        from_attributes = True
