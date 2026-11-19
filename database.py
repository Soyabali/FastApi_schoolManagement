import os

from dotenv import load_dotenv
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

load_dotenv()  # reads .env locally; on Render the variable comes from the dashboard

MISSING_DB_MESSAGE = (
    "DATABASE_URL is not set. Locally, put it in .env. "
    "On Render: open your service -> Environment -> add DATABASE_URL -> Save, rebuild, and deploy."
)

DATABASE_URL = (os.getenv("DATABASE_URL") or "").strip().strip("'\"")

# Tell SQLAlchemy to use the psycopg (v3) driver.
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)

if DATABASE_URL:
    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,  # Neon suspends idle computes; re-check connections before use
        pool_recycle=300,
    )
    SessionLocal = sessionmaker(bind=engine, autoflush=False)
else:
    # Don't crash: start anyway so /health and /docs work and the error is visible in the browser.
    similar = [k for k in os.environ if "DATABASE" in k.upper() or "DB" in k.upper()]
    print(f"ERROR: {MISSING_DB_MESSAGE} Similar variable names found: {similar or 'none'}", flush=True)
    engine = None
    SessionLocal = None


def get_db():
    if SessionLocal is None:
        raise HTTPException(status_code=503, detail=MISSING_DB_MESSAGE)
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
