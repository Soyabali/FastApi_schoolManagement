from fastapi import Depends, FastAPI
from sqlalchemy import text
from sqlalchemy.orm import Session

from auth import router as auth_router
from database import engine, get_db
from postman import router as postman_router
from school import school_routers

app = FastAPI(
    title="School Management API",
    description="Login first (`POST /auth/login`), then click **Authorize** and paste the access_token.",
)
app.include_router(auth_router)
for r in school_routers:
    app.include_router(r)
app.include_router(postman_router)


@app.api_route("/", methods=["GET", "HEAD"], tags=["Health"])
def read_root():
    return {"message": "Hello, FastAPI!"}


@app.get("/health", tags=["Health"])
def health():
    return {"status": "ok", "database_configured": engine is not None}


@app.get("/db-check", tags=["Health"])
def db_check(db: Session = Depends(get_db)):
    version = db.execute(text("SELECT version()")).scalar_one()
    return {"database": "connected", "version": version}
