"""Request/response schemas for the school API.

`XCreate`  - body for POST (required fields + database defaults)
`XUpdate`  - body for PATCH (every field optional; send only what changes)
`XOut`     - what the API returns
Allowed values (Literal) match the CHECK constraints in the database.
"""

from datetime import date, time
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, create_model

Gender = Literal["Male", "Female", "Other"]
Relationship = Literal["Father", "Mother", "Guardian"]
StaffRole = Literal["Admin", "Librarian", "Janitor", "Security", "Accountant", "Nurse"]
Weekday = Literal["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
AttendanceStatus = Literal["Present", "Absent", "Late", "Excused"]
ExamType = Literal["Mid-Term", "Final", "Quiz", "Assignment"]
FeeType = Literal["Tuition", "Transport", "Library", "Sports", "Other"]
FeeStatus = Literal["Paid", "Unpaid", "Partial"]


def make_update(name: str, create: type[BaseModel]) -> type[BaseModel]:
    """Build a PATCH schema: same fields and rules as `create`, but all optional."""
    fields = {}
    for key, info in create.model_fields.items():
        ann = Annotated[info.annotation, *info.metadata] if info.metadata else info.annotation
        fields[key] = (ann | None, None)
    return create_model(name, **fields)


class Out(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---------------- Teachers ----------------
class TeacherCreate(BaseModel):
    full_name: str = Field(min_length=1)
    email: EmailStr
    phone: str | None = None
    subject_specialization: str | None = None
    hire_date: date = Field(default_factory=date.today)
    salary: float | None = Field(default=None, ge=0)
    is_active: bool = True


class TeacherOut(Out):
    teacher_id: int
    full_name: str
    email: str
    phone: str | None
    subject_specialization: str | None
    hire_date: date | None
    salary: float | None
    is_active: bool | None


# ---------------- Staff ----------------
class StaffCreate(BaseModel):
    full_name: str = Field(min_length=1)
    email: EmailStr | None = None
    phone: str | None = None
    role: StaffRole
    hire_date: date = Field(default_factory=date.today)
    salary: float | None = Field(default=None, ge=0)
    is_active: bool = True


class StaffOut(Out):
    staff_id: int
    full_name: str
    email: str | None
    phone: str | None
    role: str
    hire_date: date | None
    salary: float | None
    is_active: bool | None


# ---------------- Classes ----------------
class ClassCreate(BaseModel):
    class_name: str = Field(min_length=1, examples=["Grade 8A"])
    grade_level: int = Field(ge=1, le=12)
    section: str = Field(min_length=1, examples=["A"])
    class_teacher_id: int | None = None
    room_number: str | None = None
    max_students: int = Field(default=40, ge=1)


class ClassOut(Out):
    class_id: int
    class_name: str
    grade_level: int
    section: str
    class_teacher_id: int | None
    room_number: str | None
    max_students: int | None


# ---------------- Subjects ----------------
class SubjectCreate(BaseModel):
    subject_name: str = Field(min_length=1)
    subject_code: str = Field(min_length=1, examples=["MATH101"])
    description: str | None = None


class SubjectOut(Out):
    subject_id: int
    subject_name: str
    subject_code: str
    description: str | None


# ---------------- Students ----------------
class StudentCreate(BaseModel):
    full_name: str = Field(min_length=1)
    date_of_birth: date
    gender: Gender
    email: EmailStr | None = None
    phone: str | None = None
    address: str | None = None
    class_id: int | None = None
    enrolled_on: date = Field(default_factory=date.today)
    is_active: bool = True


class StudentOut(Out):
    student_id: int
    full_name: str
    date_of_birth: date
    gender: str
    email: str | None
    phone: str | None
    address: str | None
    class_id: int | None
    enrolled_on: date | None
    is_active: bool | None


# ---------------- Parents ----------------
class ParentCreate(BaseModel):
    full_name: str = Field(min_length=1)
    email: EmailStr | None = None
    phone: str = Field(min_length=1)
    relationship: Relationship
    student_id: int
    address: str | None = None


class ParentOut(Out):
    parent_id: int
    full_name: str
    email: str | None
    phone: str
    relationship: str
    student_id: int
    address: str | None


# ---------------- Class subjects ----------------
class ClassSubjectCreate(BaseModel):
    class_id: int
    subject_id: int
    teacher_id: int | None = None


class ClassSubjectOut(Out):
    class_subject_id: int
    class_id: int
    subject_id: int
    teacher_id: int | None


# ---------------- Timetable ----------------
class TimetableCreate(BaseModel):
    class_id: int
    subject_id: int
    teacher_id: int
    day_of_week: Weekday
    start_time: time = Field(examples=["09:00"])
    end_time: time = Field(examples=["09:45"])
    room_number: str | None = None


class TimetableOut(Out):
    timetable_id: int
    class_id: int
    subject_id: int
    teacher_id: int
    day_of_week: str
    start_time: time
    end_time: time
    room_number: str | None


# ---------------- Attendance ----------------
class AttendanceCreate(BaseModel):
    student_id: int
    class_id: int
    attend_date: date = Field(default_factory=date.today)
    status: AttendanceStatus
    remarks: str | None = None


class AttendanceOut(Out):
    attendance_id: int
    student_id: int
    class_id: int
    attend_date: date
    status: str
    remarks: str | None


class AttendanceEntry(BaseModel):
    student_id: int
    status: AttendanceStatus
    remarks: str | None = None


class BulkAttendance(BaseModel):
    class_id: int
    attend_date: date = Field(default_factory=date.today)
    records: list[AttendanceEntry] = Field(min_length=1)


# ---------------- Exams ----------------
class ExamCreate(BaseModel):
    exam_name: str = Field(min_length=1)
    exam_type: ExamType
    class_id: int
    subject_id: int
    exam_date: date
    total_marks: float = Field(default=100, gt=0)
    pass_marks: float = Field(default=40, ge=0)


class ExamOut(Out):
    exam_id: int
    exam_name: str
    exam_type: str
    class_id: int
    subject_id: int
    exam_date: date
    total_marks: float
    pass_marks: float


# ---------------- Marks ----------------
class MarkCreate(BaseModel):
    student_id: int
    exam_id: int
    marks_obtained: float = Field(ge=0)
    grade: str | None = Field(default=None, description="Leave empty to calculate it automatically")
    remarks: str | None = None


class MarkOut(Out):
    mark_id: int
    student_id: int
    exam_id: int
    marks_obtained: float
    grade: str | None
    remarks: str | None


# ---------------- Fees ----------------
class FeeCreate(BaseModel):
    student_id: int
    fee_type: FeeType
    amount: float = Field(gt=0)
    paid_amount: float = Field(default=0, ge=0)
    due_date: date
    paid_date: date | None = None
    status: FeeStatus | None = Field(default=None, description="Leave empty to calculate it from paid_amount")


class FeeOut(Out):
    fee_id: int
    student_id: int
    fee_type: str
    amount: float
    paid_amount: float | None
    due_date: date
    paid_date: date | None
    status: str


class FeePayment(BaseModel):
    amount: float = Field(gt=0, description="Amount being paid now")
    paid_date: date = Field(default_factory=date.today)


# PATCH bodies: every field optional.
TeacherUpdate = make_update("TeacherUpdate", TeacherCreate)
StaffUpdate = make_update("StaffUpdate", StaffCreate)
ClassUpdate = make_update("ClassUpdate", ClassCreate)
SubjectUpdate = make_update("SubjectUpdate", SubjectCreate)
StudentUpdate = make_update("StudentUpdate", StudentCreate)
ParentUpdate = make_update("ParentUpdate", ParentCreate)
ClassSubjectUpdate = make_update("ClassSubjectUpdate", ClassSubjectCreate)
TimetableUpdate = make_update("TimetableUpdate", TimetableCreate)
AttendanceUpdate = make_update("AttendanceUpdate", AttendanceCreate)
ExamUpdate = make_update("ExamUpdate", ExamCreate)
MarkUpdate = make_update("MarkUpdate", MarkCreate)
FeeUpdate = make_update("FeeUpdate", FeeCreate)
