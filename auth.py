"""Authentication routes: register, login, logout, me, change password, forgot/reset password."""

import os
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from database import get_db
from models import ChangePassword, ForgotPassword, Login, Registration
from schemas import (
    ChangePasswordRequest,
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    LoginRequest,
    LoginResponse,
    MessageResponse,
    RegisterRequest,
    ResetPasswordRequest,
    UserOut,
)
from security import hash_password, hash_token, new_token, utcnow, verify_password

SESSION_HOURS = int(os.getenv("SESSION_HOURS", "24"))
RESET_TOKEN_MINUTES = int(os.getenv("RESET_TOKEN_MINUTES", "15"))
MAX_FAILED_ATTEMPTS = int(os.getenv("MAX_FAILED_ATTEMPTS", "5"))
LOCK_MINUTES = int(os.getenv("LOCK_MINUTES", "15"))
DEV_MODE = os.getenv("DEV_MODE", "false").lower() == "true"

router = APIRouter(prefix="/auth", tags=["auth"])
bearer = HTTPBearer(auto_error=False)


def client_info(request: Request) -> tuple[str | None, str | None]:
    ip = request.client.host if request.client else None
    return ip, request.headers.get("user-agent")


# ---------------------------------------------------------------------------
# Dependency: the logged-in user and their session
# ---------------------------------------------------------------------------

def get_current_session(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> Login:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not logged in or session expired",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if creds is None:
        raise unauthorized

    session = db.scalar(
        select(Login).where(
            Login.session_token == creds.credentials,
            Login.login_status == "success",
            Login.session_expires_at > utcnow(),
        )
    )
    if session is None or session.user_id is None:
        raise unauthorized
    return session


def get_current_user(
    session: Login = Depends(get_current_session),
    db: Session = Depends(get_db),
) -> Registration:
    user = db.get(Registration, session.user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Account is not active")
    return user


def end_sessions(db: Session, user_id, keep_token: str | None = None) -> None:
    """Expire all of a user's sessions, optionally keeping one."""
    now = utcnow()
    stmt = update(Login).where(
        Login.user_id == user_id,
        Login.session_token.is_not(None),
        Login.session_expires_at > now,
    )
    if keep_token:
        stmt = stmt.where(Login.session_token != keep_token)
    db.execute(stmt.values(session_expires_at=now, updated_at=now))


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(body: RegisterRequest, db: Session = Depends(get_db)):
    email = body.email.lower()
    if db.scalar(select(Registration).where(Registration.email == email)):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email is already registered")

    user = Registration(
        full_name=body.full_name,
        email=email,
        password_hash=hash_password(body.password),
        phone_number=body.phone_number,
        date_of_birth=body.date_of_birth,
        is_active=True,  # dummy app: accounts are active right away
        is_email_verified=False,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/login", response_model=LoginResponse)
def login(body: LoginRequest, request: Request, db: Session = Depends(get_db)):
    email = body.email.lower()
    ip, agent = client_info(request)
    now = utcnow()

    user = db.scalar(select(Registration).where(Registration.email == email))

    # The most recent attempt for this email tells us the failure count and lock state.
    last = db.scalar(
        select(Login).where(Login.email == email).order_by(Login.created_at.desc()).limit(1)
    )

    # Still locked?
    if last and last.is_locked and last.locked_until and last.locked_until > now:
        db.add(Login(
            email=email, user_id=user.id if user else None, login_status="blocked",
            ip_address=ip, user_agent=agent, failed_attempts=last.failed_attempts,
            is_locked=True, locked_until=last.locked_until,
        ))
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail=f"Too many failed attempts. Try again after {last.locked_until:%Y-%m-%d %H:%M} UTC",
        )

    if user is None or not verify_password(body.password, user.password_hash):
        # Continue counting only from an unlocked failed attempt; an expired lock starts over.
        previous = 0
        if last and last.login_status == "failed" and not last.is_locked:
            previous = last.failed_attempts or 0
        attempts = previous + 1
        locked = attempts >= MAX_FAILED_ATTEMPTS
        db.add(Login(
            email=email, user_id=user.id if user else None, login_status="failed",
            ip_address=ip, user_agent=agent, failed_attempts=attempts,
            is_locked=locked, locked_until=now + timedelta(minutes=LOCK_MINUTES) if locked else None,
        ))
        db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")

    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is not active")

    token = new_token()
    expires = now + timedelta(hours=SESSION_HOURS)
    db.add(Login(
        email=email, user_id=user.id, login_status="success", ip_address=ip, user_agent=agent,
        session_token=token, session_expires_at=expires, failed_attempts=0, is_locked=False,
    ))
    db.commit()
    return LoginResponse(access_token=token, expires_at=expires, user=UserOut.model_validate(user))


@router.get("/me", response_model=UserOut)
def me(user: Registration = Depends(get_current_user)):
    return user


@router.post("/logout", response_model=MessageResponse)
def logout(session: Login = Depends(get_current_session), db: Session = Depends(get_db)):
    now = utcnow()
    session.session_expires_at = now
    session.updated_at = now
    db.commit()
    return MessageResponse(message="Logged out")


@router.post("/change-password", response_model=MessageResponse)
def change_password(
    body: ChangePasswordRequest,
    request: Request,
    user: Registration = Depends(get_current_user),
    session: Login = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    if not verify_password(body.old_password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Old password is incorrect")
    if body.old_password == body.new_password:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="New password must be different")

    ip, agent = client_info(request)
    old_hash = user.password_hash
    user.password_hash = hash_password(body.new_password)
    user.updated_at = utcnow()
    db.add(ChangePassword(
        user_id=user.id, old_password_hash=old_hash, new_password_hash=user.password_hash,
        changed_via="manual", ip_address=ip, user_agent=agent,
    ))
    # Log out other devices, keep this one.
    end_sessions(db, user.id, keep_token=session.session_token)
    db.commit()
    return MessageResponse(message="Password changed. Other sessions were logged out.")


@router.post("/forgot-password", response_model=ForgotPasswordResponse)
def forgot_password(body: ForgotPasswordRequest, request: Request, db: Session = Depends(get_db)):
    email = body.email.lower()
    # Same answer whether or not the email exists, so attackers can't discover accounts.
    response = ForgotPasswordResponse(message="If that email is registered, a reset link has been sent.")

    user = db.scalar(select(Registration).where(Registration.email == email))
    if user is None:
        return response

    token = new_token()
    ip, agent = client_info(request)
    db.add(ForgotPassword(
        user_id=user.id, email=email, reset_token=hash_token(token),
        reset_token_expires_at=utcnow() + timedelta(minutes=RESET_TOKEN_MINUTES),
        ip_address=ip, user_agent=agent,
    ))
    db.commit()

    # A real app would email this token. Here it is printed, and returned in DEV_MODE.
    print(f"[forgot-password] reset token for {email}: {token}")
    if DEV_MODE:
        response.reset_token = token
    return response


@router.post("/reset-password", response_model=MessageResponse)
def reset_password(body: ResetPasswordRequest, request: Request, db: Session = Depends(get_db)):
    now = utcnow()
    reset = db.scalar(select(ForgotPassword).where(ForgotPassword.reset_token == hash_token(body.token)))
    if reset is None or reset.is_used or reset.reset_token_expires_at < now:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Reset token is invalid or expired")

    user = db.get(Registration, reset.user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Reset token is invalid or expired")

    ip, agent = client_info(request)
    old_hash = user.password_hash
    user.password_hash = hash_password(body.new_password)
    user.updated_at = now
    reset.is_used = True
    reset.used_at = now
    db.add(ChangePassword(
        user_id=user.id, old_password_hash=old_hash, new_password_hash=user.password_hash,
        changed_via="reset", ip_address=ip, user_agent=agent,
    ))
    end_sessions(db, user.id)  # log out everywhere
    db.commit()
    return MessageResponse(message="Password has been reset. Please log in with your new password.")
