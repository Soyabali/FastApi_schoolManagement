import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

load_dotenv()  # reads .env locally; on Render the variable comes from the dashboard

DATABASE_URL = (os.getenv("DATABASE_URL") or "").strip().strip("'\"")
if not DATABASE_URL:
    # Show similar variable names (never values) to catch typos like "DATABASE_URL " or "database_url".
    similar = [k for k in os.environ if "DATABASE" in k.upper() or "DB" in k.upper()]
    raise RuntimeError(
        "DATABASE_URL is not set or empty. Locally, put it in .env. "
        "On Render, add it under your service -> Environment -> Environment Variables. "
        f"Similar variable names found: {similar or 'none'}"
    )

# Tell SQLAlchemy to use the psycopg (v3) driver.
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,  # Neon suspends idle computes; re-check connections before use
    pool_recycle=300,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
