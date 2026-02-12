import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./local.db")
if DATABASE_URL.startswith("postgres://"):
    # Render may provide postgres://, but SQLAlchemy expects postgresql://
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg2://", 1)
SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key")
ADMIN_RESET_TOKEN = os.getenv("ADMIN_RESET_TOKEN", "")

UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", BASE_DIR / "uploads"))
QR_DIR = Path(os.getenv("QR_DIR", BASE_DIR / "qrcodes"))

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
QR_DIR.mkdir(parents=True, exist_ok=True)
