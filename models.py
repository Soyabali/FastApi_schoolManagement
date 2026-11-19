"""SQLAlchemy models mapped to the tables that already exist in Neon (public schema).

These models do not create tables. They only describe the existing ones.
All timestamp columns are `timestamptz`, so datetimes are time-zone aware (UTC).
"""

import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Registration(Base):
    __tablename__ = "registration"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    full_name: Mapped[str] = mapped_column(Text)
    email: Mapped[str] = mapped_column(Text, unique=True)
    password_hash: Mapped[str] = mapped_column(Text)
    phone_number: Mapped[str | None] = mapped_column(Text)
    date_of_birth: Mapped[date | None] = mapped_column(Date)
    is_active: Mapped[bool | None] = mapped_column(Boolean)
    is_email_verified: Mapped[bool | None] = mapped_column(Boolean)
    verification_token: Mapped[str | None] = mapped_column(Text)
    verification_token_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"))
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"))


class Login(Base):
    """One row per login attempt. Successful attempts also hold the session token."""

    __tablename__ = "login"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    email: Mapped[str] = mapped_column(Text)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("registration.id", ondelete="CASCADE")
    )
    login_status: Mapped[str] = mapped_column(Text)  # 'success' | 'failed' | 'blocked'
    ip_address: Mapped[str | None] = mapped_column(Text)
    user_agent: Mapped[str | None] = mapped_column(Text)
    session_token: Mapped[str | None] = mapped_column(Text, unique=True)
    session_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failed_attempts: Mapped[int | None] = mapped_column(Integer, server_default=text("0"))
    is_locked: Mapped[bool | None] = mapped_column(Boolean, server_default=text("false"))
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"))
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"))


class ChangePassword(Base):
    """History of password changes."""

    __tablename__ = "change_password"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("registration.id", ondelete="CASCADE")
    )
    old_password_hash: Mapped[str] = mapped_column(Text)
    new_password_hash: Mapped[str] = mapped_column(Text)
    changed_via: Mapped[str | None] = mapped_column(Text)  # 'manual' | 'reset' | 'admin'
    ip_address: Mapped[str | None] = mapped_column(Text)
    user_agent: Mapped[str | None] = mapped_column(Text)
    changed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"))


class ForgotPassword(Base):
    """Password reset requests. reset_token stores a SHA-256 hash of the token, not the token itself."""

    __tablename__ = "forgot_password"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("registration.id", ondelete="CASCADE")
    )
    email: Mapped[str] = mapped_column(Text)
    reset_token: Mapped[str] = mapped_column(Text, unique=True)
    reset_token_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    is_used: Mapped[bool | None] = mapped_column(Boolean, server_default=text("false"))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ip_address: Mapped[str | None] = mapped_column(Text)
    user_agent: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"))
