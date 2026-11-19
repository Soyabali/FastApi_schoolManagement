"""School management API: CRUD for every table, business rules and reports.

All school endpoints require login (Authorization: Bearer <access_token>).
"""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import case, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from auth import get_current_user
from crud import crud_router, get_or_404
from database import get_db
from school_models import (
    Attendance, ClassSubject, Exam, Fee, Mark, Parent, SchoolClass, Staff, Student, Subject, Teacher, Timetable,
)
from school_schemas import (
    AttendanceCreate, AttendanceOut, AttendanceUpdate, BulkAttendance,
    ClassCreate, ClassOut, ClassSubjectCreate, ClassSubjectOut, ClassSubjectUpdate, ClassUpdate,
    ExamCreate, ExamOut, ExamUpdate,
    FeeCreate, FeeOut, FeePayment, FeeUpdate,
    MarkCreate, MarkOut, MarkUpdate,
    ParentCreate, ParentOut, ParentUpdate,
    StaffCreate, StaffOut, StaffUpdate,
    StudentCreate, StudentOut, StudentUpdate,
    SubjectCreate, SubjectOut, SubjectUpdate,
    TeacherCreate, TeacherOut, TeacherUpdate,
    TimetableCreate, TimetableOut, TimetableUpdate,
)

LOGIN_REQUIRED = [Depends(get_current_user)]
WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]


def merged(data: dict, row) -> dict:
    """For PATCH: the row's current values overlaid with the new ones."""
    if row is None:
        return dict(data)
    current = {c.key: getattr(row, c.key) for c in row.__mapper__.column_attrs}
    return {**current, **data}


def bad_request(msg: str) -> HTTPException:
    return HTTPException(status.HTTP_400_BAD_REQUEST, msg)


# ===========================================================================
# Business rules (run before every create / update)
# ===========================================================================

def calculate_grade(obtained: float, total: float, pass_marks: float) -> str:
    if obtained < pass_marks:
        return "F"
    pct = obtained / total * 100
    if pct >= 90:
        return "A+"
    if pct >= 80:
        return "A"
    if pct >= 70:
        return "B"
    if pct >= 50:
        return "C"
    return "D"


def check_student(db: Session, data: dict, row) -> dict:
    """A class can't take more students than its max_students."""
    new_class = data.get("class_id")
    if new_class is None or (row is not None and row.class_id == new_class):
        return data
    cls = db.get(SchoolClass, new_class)
    if cls is None:
        raise bad_request(f"Class {new_class} not found")
    count = db.scalar(select(func.count()).where(Student.class_id == new_class, Student.is_active.is_not(False)))
    if cls.max_students and count >= cls.max_students:
        raise bad_request(f"{cls.class_name} is full ({count}/{cls.max_students} students)")
    return data


def check_timetable(db: Session, data: dict, row) -> dict:
    """end_time after start_time, and no clash for the class or the teacher."""
    full = merged(data, row)
    if full["end_time"] <= full["start_time"]:
        raise bad_request("end_time must be after start_time")
    overlap = (
        (Timetable.day_of_week == full["day_of_week"])
        & (Timetable.start_time < full["end_time"])
        & (Timetable.end_time > full["start_time"])
    )
    if row is not None:
        overlap &= Timetable.timetable_id != row.timetable_id
    if db.scalar(select(Timetable.timetable_id).where(overlap, Timetable.class_id == full["class_id"]).limit(1)):
        raise HTTPException(status.HTTP_409_CONFLICT, "This class already has a period at that time")
    if db.scalar(select(Timetable.timetable_id).where(overlap, Timetable.teacher_id == full["teacher_id"]).limit(1)):
        raise HTTPException(status.HTTP_409_CONFLICT, "This teacher is already teaching at that time")
    return data


def check_exam(db: Session, data: dict, row) -> dict:
    full = merged(data, row)
    if full["pass_marks"] > full["total_marks"]:
        raise bad_request("pass_marks can't be more than total_marks")
    return data


def check_mark(db: Session, data: dict, row) -> dict:
    """marks_obtained <= total_marks, and fill in the grade when it isn't given."""
    full = merged(data, row)
    exam = db.get(Exam, full["exam_id"])
    if exam is None:
        raise bad_request(f"Exam {full['exam_id']} not found")
    if full["marks_obtained"] > exam.total_marks:
        raise bad_request(f"marks_obtained can't be more than total_marks ({exam.total_marks:g})")
    if data.get("grade") is None and ("marks_obtained" in data or "exam_id" in data or row is None):
        data["grade"] = calculate_grade(full["marks_obtained"], exam.total_marks, exam.pass_marks)
    return data


def fee_status(amount: float, paid: float) -> str:
    if paid <= 0:
        return "Unpaid"
    return "Paid" if paid >= amount else "Partial"


def check_fee(db: Session, data: dict, row) -> dict:
    """paid_amount <= amount; status calculated from paid_amount unless given."""
    full = merged(data, row)
    paid = full.get("paid_amount") or 0
    if paid > full["amount"]:
        raise bad_request("paid_amount can't be more than amount")
    if data.get("status") is None:
        data["status"] = fee_status(full["amount"], paid)
        if data["status"] == "Paid" and not full.get("paid_date"):
            data["paid_date"] = date.today()
    return data


# ===========================================================================
# CRUD routers (list / get / create / update / delete) for every table
# ===========================================================================

crud_routers = [
    crud_router(model=Student, create_schema=StudentCreate, update_schema=StudentUpdate, out_schema=StudentOut,
                prefix="/students", tag="Students", label="Student",
                filters={"class_id": int, "gender": str, "is_active": bool}, before_save=check_student),
    crud_router(model=Parent, create_schema=ParentCreate, update_schema=ParentUpdate, out_schema=ParentOut,
                prefix="/parents", tag="Parents", label="Parent", filters={"student_id": int}),
    crud_router(model=Teacher, create_schema=TeacherCreate, update_schema=TeacherUpdate, out_schema=TeacherOut,
                prefix="/teachers", tag="Teachers", label="Teacher", filters={"is_active": bool}),
    crud_router(model=Staff, create_schema=StaffCreate, update_schema=StaffUpdate, out_schema=StaffOut,
                prefix="/staff", tag="Staff", label="Staff member", filters={"role": str, "is_active": bool}),
    crud_router(model=SchoolClass, create_schema=ClassCreate, update_schema=ClassUpdate, out_schema=ClassOut,
                prefix="/classes", tag="Classes", label="Class", filters={"grade_level": int},
                order_by=SchoolClass.class_name),
    crud_router(model=Subject, create_schema=SubjectCreate, update_schema=SubjectUpdate, out_schema=SubjectOut,
                prefix="/subjects", tag="Subjects", label="Subject"),
    crud_router(model=ClassSubject, create_schema=ClassSubjectCreate, update_schema=ClassSubjectUpdate,
                out_schema=ClassSubjectOut, prefix="/class-subjects", tag="Class subjects", label="Class subject",
                filters={"class_id": int, "subject_id": int, "teacher_id": int}),
    crud_router(model=Timetable, create_schema=TimetableCreate, update_schema=TimetableUpdate,
                out_schema=TimetableOut, prefix="/timetable", tag="Timetable", label="Timetable entry",
                filters={"class_id": int, "teacher_id": int, "day_of_week": str}, before_save=check_timetable),
    crud_router(model=Attendance, create_schema=AttendanceCreate, update_schema=AttendanceUpdate,
                out_schema=AttendanceOut, prefix="/attendance", tag="Attendance", label="Attendance record",
                filters={"student_id": int, "class_id": int, "attend_date": date, "status": str},
                order_by=Attendance.attend_date.desc()),
    crud_router(model=Exam, create_schema=ExamCreate, update_schema=ExamUpdate, out_schema=ExamOut,
                prefix="/exams", tag="Exams", label="Exam",
                filters={"class_id": int, "subject_id": int, "exam_type": str}, before_save=check_exam),
    crud_router(model=Mark, create_schema=MarkCreate, update_schema=MarkUpdate, out_schema=MarkOut,
                prefix="/marks", tag="Marks", label="Mark", filters={"student_id": int, "exam_id": int},
                before_save=check_mark),
    crud_router(model=Fee, create_schema=FeeCreate, update_schema=FeeUpdate, out_schema=FeeOut,
                prefix="/fees", tag="Fees", label="Fee", filters={"student_id": int, "status": str, "fee_type": str},
                before_save=check_fee),
]


# ===========================================================================
# Extra endpoints: actions and reports
# ===========================================================================

router = APIRouter()


@router.get("/dashboard", tags=["Reports"], summary="School overview: counts, today's attendance, fees")
def dashboard(db: Session = Depends(get_db)):
    today = date.today()
    count = lambda model, *where: db.scalar(select(func.count()).select_from(model).where(*where))  # noqa: E731
    attendance_today = dict(
        db.execute(select(Attendance.status, func.count()).where(Attendance.attend_date == today)
                   .group_by(Attendance.status)).all()
    )
    total, collected = db.execute(
        select(func.coalesce(func.sum(Fee.amount), 0), func.coalesce(func.sum(Fee.paid_amount), 0))
    ).one()
    return {
        "students": count(Student, Student.is_active.is_not(False)),
        "teachers": count(Teacher, Teacher.is_active.is_not(False)),
        "staff": count(Staff, Staff.is_active.is_not(False)),
        "classes": count(SchoolClass),
        "subjects": count(Subject),
        "attendance_today": {"date": today, **{s: attendance_today.get(s, 0) for s in
                                               ["Present", "Absent", "Late", "Excused"]}},
        "fees": {"total": float(total), "collected": float(collected), "pending": float(total - collected),
                 "overdue_count": count(Fee, Fee.status != "Paid", Fee.due_date < today)},
    }


# ---------------- Students ----------------

@router.get("/students/{student_id}/profile", tags=["Students"],
            summary="Everything about one student: class, parents, attendance and fees")
def student_profile(student_id: int, db: Session = Depends(get_db)):
    student = get_or_404(db, Student, student_id, "Student")
    cls = db.get(SchoolClass, student.class_id) if student.class_id else None
    class_teacher = db.get(Teacher, cls.class_teacher_id) if cls and cls.class_teacher_id else None
    parents = db.scalars(select(Parent).where(Parent.student_id == student_id)).all()
    att = dict(db.execute(select(Attendance.status, func.count()).where(Attendance.student_id == student_id)
                          .group_by(Attendance.status)).all())
    days = sum(att.values())
    present = att.get("Present", 0) + att.get("Late", 0)
    fees = db.scalars(select(Fee).where(Fee.student_id == student_id).order_by(Fee.due_date)).all()
    return {
        "student": StudentOut.model_validate(student),
        "class": {"class_id": cls.class_id, "class_name": cls.class_name, "room_number": cls.room_number,
                  "class_teacher": class_teacher.full_name if class_teacher else None} if cls else None,
        "parents": [ParentOut.model_validate(p) for p in parents],
        "attendance": {"days_recorded": days, **{s: att.get(s, 0) for s in ["Present", "Absent", "Late", "Excused"]},
                       "attendance_percent": round(present / days * 100, 1) if days else None},
        "fees": {"total": sum(f.amount for f in fees), "paid": sum(f.paid_amount or 0 for f in fees),
                 "pending": sum(f.amount - (f.paid_amount or 0) for f in fees),
                 "items": [FeeOut.model_validate(f) for f in fees]},
    }


@router.get("/students/{student_id}/report-card", tags=["Students"],
            summary="All exam results for a student, with totals and percentage")
def report_card(student_id: int, exam_type: str | None = None, db: Session = Depends(get_db)):
    student = get_or_404(db, Student, student_id, "Student")
    stmt = (select(Exam, Subject.subject_name, Mark)
            .join(Mark, Mark.exam_id == Exam.exam_id)
            .join(Subject, Subject.subject_id == Exam.subject_id)
            .where(Mark.student_id == student_id)
            .order_by(Exam.exam_date))
    if exam_type:
        stmt = stmt.where(Exam.exam_type == exam_type)
    results = [
        {"exam_id": e.exam_id, "exam_name": e.exam_name, "exam_type": e.exam_type, "subject": subject,
         "exam_date": e.exam_date, "marks_obtained": m.marks_obtained, "total_marks": e.total_marks,
         "percent": round(m.marks_obtained / e.total_marks * 100, 1), "grade": m.grade,
         "result": "Pass" if m.marks_obtained >= e.pass_marks else "Fail", "remarks": m.remarks}
        for e, subject, m in db.execute(stmt).all()
    ]
    obtained = sum(r["marks_obtained"] for r in results)
    total = sum(r["total_marks"] for r in results)
    pct = round(obtained / total * 100, 1) if total else None
    return {
        "student_id": student.student_id, "full_name": student.full_name, "results": results,
        "summary": {"exams": len(results), "marks_obtained": obtained, "total_marks": total, "percent": pct,
                    "overall_grade": calculate_grade(obtained, total, 0) if total else None,
                    "failed_exams": sum(r["result"] == "Fail" for r in results)},
    }


# ---------------- Classes ----------------

@router.get("/classes/{class_id}/students", tags=["Classes"], response_model=list[StudentOut],
            summary="Students in a class")
def class_students(class_id: int, db: Session = Depends(get_db)):
    get_or_404(db, SchoolClass, class_id, "Class")
    return db.scalars(select(Student).where(Student.class_id == class_id).order_by(Student.full_name)).all()


def timetable_rows(db: Session, where):
    day_order = case({d: i for i, d in enumerate(WEEKDAYS)}, value=Timetable.day_of_week)
    stmt = (select(Timetable, SchoolClass.class_name, Subject.subject_name, Teacher.full_name)
            .join(SchoolClass, SchoolClass.class_id == Timetable.class_id)
            .join(Subject, Subject.subject_id == Timetable.subject_id)
            .join(Teacher, Teacher.teacher_id == Timetable.teacher_id)
            .where(where).order_by(day_order, Timetable.start_time))
    week: dict[str, list] = {d: [] for d in WEEKDAYS}
    for t, class_name, subject, teacher in db.execute(stmt).all():
        week[t.day_of_week].append({
            "timetable_id": t.timetable_id, "start_time": t.start_time, "end_time": t.end_time,
            "class": class_name, "subject": subject, "teacher": teacher, "room_number": t.room_number,
        })
    return week


@router.get("/classes/{class_id}/timetable", tags=["Classes"], summary="Weekly timetable of a class")
def class_timetable(class_id: int, db: Session = Depends(get_db)):
    cls = get_or_404(db, SchoolClass, class_id, "Class")
    return {"class_id": class_id, "class_name": cls.class_name,
            "week": timetable_rows(db, Timetable.class_id == class_id)}


@router.get("/classes/{class_id}/attendance", tags=["Classes"],
            summary="Attendance sheet of a class for one day (includes students not marked yet)")
def class_attendance(class_id: int, attend_date: date = Query(default_factory=date.today),
                     db: Session = Depends(get_db)):
    cls = get_or_404(db, SchoolClass, class_id, "Class")
    stmt = (select(Student.student_id, Student.full_name, Attendance.status, Attendance.remarks)
            .outerjoin(Attendance, (Attendance.student_id == Student.student_id)
                       & (Attendance.attend_date == attend_date))
            .where(Student.class_id == class_id, Student.is_active.is_not(False))
            .order_by(Student.full_name))
    sheet = [{"student_id": sid, "full_name": name, "status": st or "Not marked", "remarks": rm}
             for sid, name, st, rm in db.execute(stmt).all()]
    summary: dict[str, int] = {}
    for row in sheet:
        summary[row["status"]] = summary.get(row["status"], 0) + 1
    return {"class_id": class_id, "class_name": cls.class_name, "date": attend_date,
            "summary": summary, "students": sheet}


# ---------------- Teachers ----------------

@router.get("/teachers/{teacher_id}/timetable", tags=["Teachers"], summary="Weekly timetable of a teacher")
def teacher_timetable(teacher_id: int, db: Session = Depends(get_db)):
    teacher = get_or_404(db, Teacher, teacher_id, "Teacher")
    return {"teacher_id": teacher_id, "full_name": teacher.full_name,
            "week": timetable_rows(db, Timetable.teacher_id == teacher_id)}


@router.get("/teachers/{teacher_id}/classes", tags=["Teachers"],
            summary="Classes and subjects a teacher teaches, and classes they are class teacher of")
def teacher_classes(teacher_id: int, db: Session = Depends(get_db)):
    teacher = get_or_404(db, Teacher, teacher_id, "Teacher")
    teaches = db.execute(
        select(SchoolClass.class_id, SchoolClass.class_name, Subject.subject_name)
        .join(ClassSubject, ClassSubject.class_id == SchoolClass.class_id)
        .join(Subject, Subject.subject_id == ClassSubject.subject_id)
        .where(ClassSubject.teacher_id == teacher_id).order_by(SchoolClass.class_name)
    ).all()
    class_teacher_of = db.scalars(select(SchoolClass.class_name).where(SchoolClass.class_teacher_id == teacher_id)).all()
    return {"teacher_id": teacher_id, "full_name": teacher.full_name, "class_teacher_of": class_teacher_of,
            "teaches": [{"class_id": c, "class_name": n, "subject": s} for c, n, s in teaches]}


# ---------------- Attendance ----------------

@router.post("/attendance/bulk", tags=["Attendance"],
             summary="Mark attendance for a whole class at once (re-sending updates it)")
def bulk_attendance(body: BulkAttendance, db: Session = Depends(get_db)):
    get_or_404(db, SchoolClass, body.class_id, "Class")
    ids = {r.student_id for r in body.records}
    in_class = set(db.scalars(select(Student.student_id).where(Student.student_id.in_(ids),
                                                               Student.class_id == body.class_id)).all())
    if missing := sorted(ids - in_class):
        raise bad_request(f"These students are not in class {body.class_id}: {missing}")
    rows = [{"student_id": r.student_id, "class_id": body.class_id, "attend_date": body.attend_date,
             "status": r.status, "remarks": r.remarks} for r in body.records]
    stmt = insert(Attendance).values(rows)
    stmt = stmt.on_conflict_do_update(  # one record per student per day
        index_elements=["student_id", "attend_date"],
        set_={"status": stmt.excluded.status, "remarks": stmt.excluded.remarks, "class_id": stmt.excluded.class_id},
    )
    db.execute(stmt)
    db.commit()
    return {"message": f"Attendance saved for {len(rows)} students", "date": body.attend_date}


# ---------------- Exams ----------------

@router.get("/exams/{exam_id}/results", tags=["Exams"], summary="Ranked results of one exam, with class average")
def exam_results(exam_id: int, db: Session = Depends(get_db)):
    exam = get_or_404(db, Exam, exam_id, "Exam")
    rows = db.execute(
        select(Student.student_id, Student.full_name, Mark.marks_obtained, Mark.grade)
        .join(Mark, Mark.student_id == Student.student_id)
        .where(Mark.exam_id == exam_id).order_by(Mark.marks_obtained.desc())
    ).all()
    results = [{"rank": i, "student_id": sid, "full_name": name, "marks_obtained": m, "grade": g,
                "result": "Pass" if m >= exam.pass_marks else "Fail"}
               for i, (sid, name, m, g) in enumerate(rows, start=1)]
    scores = [r["marks_obtained"] for r in results]
    return {
        "exam": ExamOut.model_validate(exam),
        "summary": {"students": len(scores),
                    "average": round(sum(scores) / len(scores), 2) if scores else None,
                    "highest": max(scores, default=None), "lowest": min(scores, default=None),
                    "passed": sum(r["result"] == "Pass" for r in results),
                    "failed": sum(r["result"] == "Fail" for r in results)},
        "results": results,
    }


# ---------------- Fees ----------------

@router.get("/fees/pending", tags=["Fees"], summary="All unpaid or partly paid fees, oldest due date first")
def pending_fees(overdue_only: bool = False, db: Session = Depends(get_db)):
    today = date.today()
    stmt = (select(Fee, Student.full_name).join(Student, Student.student_id == Fee.student_id)
            .where(Fee.status != "Paid").order_by(Fee.due_date))
    if overdue_only:
        stmt = stmt.where(Fee.due_date < today)
    return [{**FeeOut.model_validate(f).model_dump(), "student_name": name,
             "balance": f.amount - (f.paid_amount or 0), "overdue": f.due_date < today}
            for f, name in db.execute(stmt).all()]


@router.post("/fees/{fee_id}/pay", tags=["Fees"], response_model=FeeOut,
             summary="Record a payment; status becomes Partial or Paid automatically")
def pay_fee(fee_id: int, body: FeePayment, db: Session = Depends(get_db)):
    fee = get_or_404(db, Fee, fee_id, "Fee")
    balance = fee.amount - (fee.paid_amount or 0)
    if balance <= 0:
        raise bad_request("This fee is already fully paid")
    if body.amount > balance:
        raise bad_request(f"Payment is more than the balance due ({balance:g})")
    fee.paid_amount = (fee.paid_amount or 0) + body.amount
    fee.status = fee_status(fee.amount, fee.paid_amount)
    fee.paid_date = body.paid_date
    db.commit()
    db.refresh(fee)
    return fee


# One parent router that requires login for every school endpoint.
# Custom routes go first so /fees/pending isn't read as /fees/{id}.
school_api = APIRouter(dependencies=LOGIN_REQUIRED)
for r in [router, *crud_routers]:
    school_api.include_router(r)
school_routers = [school_api]
