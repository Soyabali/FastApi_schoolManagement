"""SQLAlchemy models for the school management tables that already exist in Neon.

These classes do not create or change tables. They describe the existing ones.
"""

from datetime import date, time

from sqlalchemy import Boolean, Date, ForeignKey, Integer, Numeric, Text, Time
from sqlalchemy.orm import Mapped, mapped_column

from models import Base

# Numeric columns are returned as float so the JSON shows numbers, not strings.
Money = Numeric(asdecimal=False)


class Teacher(Base):
    __tablename__ = "teachers"

    teacher_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    full_name: Mapped[str] = mapped_column(Text)
    email: Mapped[str] = mapped_column(Text, unique=True)
    phone: Mapped[str | None] = mapped_column(Text)
    subject_specialization: Mapped[str | None] = mapped_column(Text)
    hire_date: Mapped[date | None] = mapped_column(Date)
    salary: Mapped[float | None] = mapped_column(Money)
    is_active: Mapped[bool | None] = mapped_column(Boolean)


class Staff(Base):
    __tablename__ = "staff"

    staff_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    full_name: Mapped[str] = mapped_column(Text)
    email: Mapped[str | None] = mapped_column(Text, unique=True)
    phone: Mapped[str | None] = mapped_column(Text)
    role: Mapped[str] = mapped_column(Text)
    hire_date: Mapped[date | None] = mapped_column(Date)
    salary: Mapped[float | None] = mapped_column(Money)
    is_active: Mapped[bool | None] = mapped_column(Boolean)


class SchoolClass(Base):
    __tablename__ = "classes"

    class_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    class_name: Mapped[str] = mapped_column(Text, unique=True)
    grade_level: Mapped[int] = mapped_column(Integer)
    section: Mapped[str] = mapped_column(Text)
    class_teacher_id: Mapped[int | None] = mapped_column(ForeignKey("teachers.teacher_id", ondelete="SET NULL"))
    room_number: Mapped[str | None] = mapped_column(Text)
    max_students: Mapped[int | None] = mapped_column(Integer)


class Subject(Base):
    __tablename__ = "subjects"

    subject_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    subject_name: Mapped[str] = mapped_column(Text, unique=True)
    subject_code: Mapped[str] = mapped_column(Text, unique=True)
    description: Mapped[str | None] = mapped_column(Text)


class Student(Base):
    __tablename__ = "students"

    student_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    full_name: Mapped[str] = mapped_column(Text)
    date_of_birth: Mapped[date] = mapped_column(Date)
    gender: Mapped[str] = mapped_column(Text)
    email: Mapped[str | None] = mapped_column(Text, unique=True)
    phone: Mapped[str | None] = mapped_column(Text)
    address: Mapped[str | None] = mapped_column(Text)
    class_id: Mapped[int | None] = mapped_column(ForeignKey("classes.class_id", ondelete="SET NULL"))
    enrolled_on: Mapped[date | None] = mapped_column(Date)
    is_active: Mapped[bool | None] = mapped_column(Boolean)


class Parent(Base):
    __tablename__ = "parents"

    parent_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    full_name: Mapped[str] = mapped_column(Text)
    email: Mapped[str | None] = mapped_column(Text, unique=True)
    phone: Mapped[str] = mapped_column(Text)
    relationship: Mapped[str] = mapped_column(Text)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.student_id", ondelete="CASCADE"))
    address: Mapped[str | None] = mapped_column(Text)


class ClassSubject(Base):
    """Which subjects a class studies, and which teacher teaches each one."""

    __tablename__ = "class_subjects"

    class_subject_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    class_id: Mapped[int] = mapped_column(ForeignKey("classes.class_id", ondelete="CASCADE"))
    subject_id: Mapped[int] = mapped_column(ForeignKey("subjects.subject_id", ondelete="CASCADE"))
    teacher_id: Mapped[int | None] = mapped_column(ForeignKey("teachers.teacher_id", ondelete="SET NULL"))


class Timetable(Base):
    __tablename__ = "timetable"

    timetable_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    class_id: Mapped[int] = mapped_column(ForeignKey("classes.class_id", ondelete="CASCADE"))
    subject_id: Mapped[int] = mapped_column(ForeignKey("subjects.subject_id", ondelete="CASCADE"))
    teacher_id: Mapped[int] = mapped_column(ForeignKey("teachers.teacher_id", ondelete="CASCADE"))
    day_of_week: Mapped[str] = mapped_column(Text)
    start_time: Mapped[time] = mapped_column(Time)
    end_time: Mapped[time] = mapped_column(Time)
    room_number: Mapped[str | None] = mapped_column(Text)


class Attendance(Base):
    __tablename__ = "attendance"

    attendance_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.student_id", ondelete="CASCADE"))
    class_id: Mapped[int] = mapped_column(ForeignKey("classes.class_id", ondelete="CASCADE"))
    attend_date: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(Text)
    remarks: Mapped[str | None] = mapped_column(Text)


class Exam(Base):
    __tablename__ = "exams"

    exam_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    exam_name: Mapped[str] = mapped_column(Text)
    exam_type: Mapped[str] = mapped_column(Text)
    class_id: Mapped[int] = mapped_column(ForeignKey("classes.class_id", ondelete="CASCADE"))
    subject_id: Mapped[int] = mapped_column(ForeignKey("subjects.subject_id", ondelete="CASCADE"))
    exam_date: Mapped[date] = mapped_column(Date)
    total_marks: Mapped[float] = mapped_column(Money)
    pass_marks: Mapped[float] = mapped_column(Money)


class Mark(Base):
    __tablename__ = "marks"

    mark_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.student_id", ondelete="CASCADE"))
    exam_id: Mapped[int] = mapped_column(ForeignKey("exams.exam_id", ondelete="CASCADE"))
    marks_obtained: Mapped[float] = mapped_column(Money)
    grade: Mapped[str | None] = mapped_column(Text)
    remarks: Mapped[str | None] = mapped_column(Text)


class Fee(Base):
    __tablename__ = "fees"

    fee_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.student_id", ondelete="CASCADE"))
    fee_type: Mapped[str] = mapped_column(Text)
    amount: Mapped[float] = mapped_column(Money)
    paid_amount: Mapped[float | None] = mapped_column(Money)
    due_date: Mapped[date] = mapped_column(Date)
    paid_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(Text)
