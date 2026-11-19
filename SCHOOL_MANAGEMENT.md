# School Management API: Guide

A FastAPI backend for the **school management database in Neon PostgreSQL**. It covers students, parents, teachers, staff, classes, subjects, timetable, attendance, exams, marks and fees.

> The diagrams use **Mermaid**. They render on GitHub, and in VS Code after installing the extension *"Markdown Preview Mermaid Support"* (then press `Cmd+Shift+V`).

---

## Contents
1. [Quick start](#1-quick-start)
2. [System architecture](#2-system-architecture)
3. [ER diagram](#3-er-diagram)
4. [Tables explained](#4-tables-explained)
5. [Complete school flow](#5-complete-school-flow)
6. [API endpoints](#6-api-endpoints)
7. [Business rules](#7-business-rules-enforced-by-the-api)
8. [Step-by-step examples](#8-step-by-step-examples)
9. [Errors](#9-error-codes)
10. [Project files](#10-project-files)

---

## 1. Quick start

```bash
cd /Users/synergy/Desktop/neondb
source .venv/bin/activate
pip install -r requirements.txt        # first time only
fastapi dev main.py --port 8000
```

Open **http://127.0.0.1:8000/docs**, then:

1. `POST /auth/login` with your email and password, and copy the `access_token`.
2. Click **Authorize** (top right), paste the token, and click **Authorize**.
3. Every school endpoint now works. Without the token they return **401**.

---

## 2. System architecture

```mermaid
flowchart LR
    U[User / Frontend / Swagger /docs] -->|HTTP + Bearer token| API

    subgraph API[FastAPI app - main.py]
        AUTH[auth.py<br/>register, login, passwords]
        SCH[school.py<br/>rules + reports]
        CRUD[crud.py<br/>list / get / create / update / delete]
        SCH --> CRUD
    end

    AUTH -->|SQLAlchemy + psycopg| DB[(Neon PostgreSQL<br/>neondb)]
    CRUD --> DB
    SCH --> DB
```

**Request lifecycle**

```mermaid
sequenceDiagram
    participant C as Client
    participant A as FastAPI
    participant V as Pydantic validation
    participant R as Business rules
    participant D as Neon DB

    C->>A: POST /students (Bearer token, JSON)
    A->>D: Check session token in login table
    D-->>A: Valid user (or 401)
    A->>V: Validate body (types, gender, email...)
    V-->>A: OK (or 422)
    A->>R: check_student (class not full?)
    R->>D: Count students in class
    R-->>A: OK (or 400)
    A->>D: INSERT INTO students
    D-->>A: New row (or 409 duplicate / 400 bad link)
    A-->>C: 201 Created + student JSON
```

---

## 3. ER diagram

```mermaid
erDiagram
    TEACHERS ||--o{ CLASSES : "is class teacher of"
    TEACHERS ||--o{ CLASS_SUBJECTS : teaches
    TEACHERS ||--o{ TIMETABLE : "takes period"

    CLASSES ||--o{ STUDENTS : has
    CLASSES ||--o{ CLASS_SUBJECTS : studies
    CLASSES ||--o{ TIMETABLE : "has periods"
    CLASSES ||--o{ ATTENDANCE : records
    CLASSES ||--o{ EXAMS : holds

    SUBJECTS ||--o{ CLASS_SUBJECTS : "taught in"
    SUBJECTS ||--o{ TIMETABLE : "scheduled in"
    SUBJECTS ||--o{ EXAMS : "examined in"

    STUDENTS ||--o{ PARENTS : "has"
    STUDENTS ||--o{ ATTENDANCE : "is marked"
    STUDENTS ||--o{ MARKS : scores
    STUDENTS ||--o{ FEES : pays

    EXAMS ||--o{ MARKS : produces

    TEACHERS {
        int teacher_id PK
        text full_name
        text email UK
        text phone
        text subject_specialization
        date hire_date
        numeric salary
        bool is_active
    }
    STAFF {
        int staff_id PK
        text full_name
        text email UK
        text phone
        text role "Admin|Librarian|Janitor|Security|Accountant|Nurse"
        date hire_date
        numeric salary
        bool is_active
    }
    CLASSES {
        int class_id PK
        text class_name UK
        int grade_level
        text section
        int class_teacher_id FK
        text room_number
        int max_students "default 40"
    }
    SUBJECTS {
        int subject_id PK
        text subject_name UK
        text subject_code UK
        text description
    }
    STUDENTS {
        int student_id PK
        text full_name
        date date_of_birth
        text gender "Male|Female|Other"
        text email UK
        text phone
        text address
        int class_id FK
        date enrolled_on
        bool is_active
    }
    PARENTS {
        int parent_id PK
        text full_name
        text email UK
        text phone
        text relationship "Father|Mother|Guardian"
        int student_id FK
        text address
    }
    CLASS_SUBJECTS {
        int class_subject_id PK
        int class_id FK
        int subject_id FK
        int teacher_id FK
    }
    TIMETABLE {
        int timetable_id PK
        int class_id FK
        int subject_id FK
        int teacher_id FK
        text day_of_week "Monday..Friday"
        time start_time
        time end_time
        text room_number
    }
    ATTENDANCE {
        int attendance_id PK
        int student_id FK
        int class_id FK
        date attend_date "unique per student"
        text status "Present|Absent|Late|Excused"
        text remarks
    }
    EXAMS {
        int exam_id PK
        text exam_name
        text exam_type "Mid-Term|Final|Quiz|Assignment"
        int class_id FK
        int subject_id FK
        date exam_date
        numeric total_marks "default 100"
        numeric pass_marks "default 40"
    }
    MARKS {
        int mark_id PK
        int student_id FK
        int exam_id FK
        numeric marks_obtained
        text grade
        text remarks
    }
    FEES {
        int fee_id PK
        int student_id FK
        text fee_type "Tuition|Transport|Library|Sports|Other"
        numeric amount
        numeric paid_amount
        date due_date
        date paid_date
        text status "Paid|Unpaid|Partial"
    }
```

`STAFF` (non-teaching staff) has no links to other tables.

### What happens on delete

| When you delete… | These are deleted too (CASCADE) | These are kept, link set to empty (SET NULL) |
|---|---|---|
| a **student** | parents, attendance, marks, fees | – |
| a **class** | class_subjects, timetable, attendance, exams (→ their marks) | students (`class_id` becomes null) |
| a **subject** | class_subjects, timetable, exams (→ their marks) | – |
| a **teacher** | timetable periods | classes (`class_teacher_id`), class_subjects (`teacher_id`) |
| an **exam** | marks | – |

> ⚠️ Deleting is permanent. To remove a student or teacher but keep their history, set `is_active` to `false` with **PATCH** instead.

### Login tables (separate from the school data)

```mermaid
erDiagram
    REGISTRATION ||--o{ LOGIN : "login attempts / sessions"
    REGISTRATION ||--o{ CHANGE_PASSWORD : "password history"
    REGISTRATION ||--o{ FORGOT_PASSWORD : "reset requests"
```
These control **who can use the API**. See [README.md](README.md).

---

## 4. Tables explained

| Table | Purpose | Unique rule |
|---|---|---|
| `teachers` | Teaching staff | email |
| `staff` | Non-teaching staff (admin, librarian…) | email |
| `classes` | A class/section, e.g. *Grade 5A*, with an optional class teacher | class_name |
| `subjects` | Subjects offered, e.g. Mathematics (MATH101) | name, code |
| `students` | Students, each in one class | email |
| `parents` | Parent/guardian contacts of a student | email |
| `class_subjects` | Which subjects a class studies and **who teaches** each | (class, subject) |
| `timetable` | Weekly periods: class + subject + teacher + day + time | – |
| `attendance` | Daily status of each student | (student, date) |
| `exams` | An exam for one class and one subject | – |
| `marks` | A student's score in an exam | (student, exam) |
| `fees` | Fee bills and payments of a student | – |

---

## 5. Complete school flow

### 5.1 Setting up the school year

```mermaid
flowchart TD
    A[1. Add teachers<br/>POST /teachers] --> B[2. Add subjects<br/>POST /subjects]
    B --> C[3. Create classes + class teacher<br/>POST /classes]
    C --> D[4. Assign subjects and teachers to classes<br/>POST /class-subjects]
    D --> E[5. Build weekly timetable<br/>POST /timetable]
    A2[Add non-teaching staff<br/>POST /staff]
    E --> F[School is ready for admissions]
```

### 5.2 Student admission

```mermaid
flowchart TD
    A[Admit student<br/>POST /students with class_id] --> B{Is the class full?}
    B -- yes --> X[400: class is full<br/>choose another class]
    B -- no --> C[Student created]
    C --> D[Add parents / guardians<br/>POST /parents]
    D --> E[Create fee bills<br/>POST /fees]
    E --> F[View the profile<br/>GET /students/id/profile]
```

### 5.3 Daily routine

```mermaid
flowchart LR
    A[Check class timetable<br/>GET /classes/id/timetable] --> B[Mark attendance for the class<br/>POST /attendance/bulk]
    B --> C[See today's sheet<br/>GET /classes/id/attendance]
    C --> D[Overview<br/>GET /dashboard]
```

### 5.4 Exams and results

```mermaid
flowchart TD
    A[Create exam for a class + subject<br/>POST /exams] --> B[Enter each student's marks<br/>POST /marks]
    B --> C{grade sent?}
    C -- no --> D[Grade calculated automatically]
    C -- yes --> E[Your grade is kept]
    D --> F[Exam results, ranked<br/>GET /exams/id/results]
    E --> F
    F --> G[Report card per student<br/>GET /students/id/report-card]
```

### 5.5 Fee collection

```mermaid
stateDiagram-v2
    [*] --> Unpaid: POST /fees
    Unpaid --> Partial: POST /fees/id/pay (part)
    Unpaid --> Paid: POST /fees/id/pay (full)
    Partial --> Partial: pay more (still balance)
    Partial --> Paid: pay remaining balance
    Paid --> [*]
```

Use `GET /fees/pending` to see who still owes money, and `GET /fees/pending?overdue_only=true` for bills past their due date.

---

## 6. API endpoints

All endpoints below need `Authorization: Bearer <access_token>`.

### Standard endpoints (every table)

Each of these resources gets the same 5 endpoints:

`/students` · `/parents` · `/teachers` · `/staff` · `/classes` · `/subjects` · `/class-subjects` · `/timetable` · `/attendance` · `/exams` · `/marks` · `/fees`

| Method | URL | Does |
|---|---|---|
| GET | `/students` | List (supports `skip`, `limit`, and filters) |
| GET | `/students/{id}` | Get one |
| POST | `/students` | Create |
| PATCH | `/students/{id}` | Update, sending **only the fields that change** |
| DELETE | `/students/{id}` | Delete (see the cascade table above) |

**Filters available on the list endpoints**

| List | Filters |
|---|---|
| `/students` | `class_id`, `gender`, `is_active` |
| `/parents` | `student_id` |
| `/teachers` | `is_active` |
| `/staff` | `role`, `is_active` |
| `/classes` | `grade_level` |
| `/class-subjects` | `class_id`, `subject_id`, `teacher_id` |
| `/timetable` | `class_id`, `teacher_id`, `day_of_week` |
| `/attendance` | `student_id`, `class_id`, `attend_date`, `status` |
| `/exams` | `class_id`, `subject_id`, `exam_type` |
| `/marks` | `student_id`, `exam_id` |
| `/fees` | `student_id`, `status`, `fee_type` |

Example: `GET /students?class_id=1&is_active=true`

### Reports and actions

| Method | URL | Does |
|---|---|---|
| GET | `/dashboard` | Counts, today's attendance, fee totals and overdue count |
| GET | `/students/{id}/profile` | Student + class + class teacher + parents + attendance % + fees |
| GET | `/students/{id}/report-card` | All marks, % per exam, total %, overall grade (`?exam_type=Final` optional) |
| GET | `/classes/{id}/students` | Students in a class |
| GET | `/classes/{id}/timetable` | Weekly timetable grouped by day |
| GET | `/classes/{id}/attendance?attend_date=YYYY-MM-DD` | Day sheet, including students **not marked** yet |
| GET | `/teachers/{id}/timetable` | A teacher's weekly schedule |
| GET | `/teachers/{id}/classes` | Classes/subjects a teacher teaches and classes they lead |
| POST | `/attendance/bulk` | Mark a whole class at once. Sending again **updates** it |
| GET | `/exams/{id}/results` | Ranked results, average, highest, lowest, pass/fail count |
| GET | `/fees/pending` | Unpaid/partial fees with balance (`?overdue_only=true`) |
| POST | `/fees/{id}/pay` | Record a payment. Status becomes Partial/Paid automatically |

---

## 7. Business rules enforced by the API

| Area | Rule | Error if broken |
|---|---|---|
| Students | A class can't take more than `max_students` active students | 400 |
| Timetable | `end_time` must be after `start_time` | 400 |
| Timetable | A class can't have two periods at the same time | 409 |
| Timetable | A teacher can't teach two periods at the same time | 409 |
| Exams | `pass_marks` ≤ `total_marks` | 400 |
| Marks | `marks_obtained` ≤ exam's `total_marks` | 400 |
| Marks | One mark per student per exam | 409 |
| Marks | Grade is auto-calculated if you don't send one (see below) | – |
| Attendance | One record per student per day; bulk only for students in that class | 400 / 409 |
| Fees | `paid_amount` ≤ `amount`; payment can't exceed balance | 400 |
| Fees | Status auto-set: 0 paid → *Unpaid*, part → *Partial*, all → *Paid* (+ `paid_date`) | – |
| All | Fixed choices (gender, relationship, role, weekday, status, exam/fee type) are checked | 422 |

**Grade scale** (used when no grade is sent):

| Condition | Grade |
|---|---|
| marks < pass_marks | **F** |
| ≥ 90 % | **A+** |
| ≥ 80 % | **A** |
| ≥ 70 % | **B** |
| ≥ 50 % | **C** |
| below 50 % but passed | **D** |

To change it, edit `calculate_grade()` in [school.py](school.py).

---

## 8. Step-by-step examples

Set these once in your terminal (replace the token with yours):
```bash
API=http://127.0.0.1:8000
TOKEN=<paste access_token>
H=(-H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json")
```

**Create a teacher**
```bash
curl -X POST $API/teachers "${H[@]}" -d '{
  "full_name": "Priya Sharma", "email": "priya@school.com",
  "phone": "9876543210", "subject_specialization": "Mathematics", "salary": 45000
}'
```

**Create a class with that teacher as class teacher**
```bash
curl -X POST $API/classes "${H[@]}" -d '{
  "class_name": "Grade 8A", "grade_level": 8, "section": "A",
  "class_teacher_id": 7, "room_number": "201", "max_students": 35
}'
```

**Admit a student**
```bash
curl -X POST $API/students "${H[@]}" -d '{
  "full_name": "Aman Verma", "date_of_birth": "2012-05-10",
  "gender": "Male", "class_id": 7, "phone": "9000000000"
}'
```

**Add a parent**
```bash
curl -X POST $API/parents "${H[@]}" -d '{
  "full_name": "Rakesh Verma", "phone": "9111111111",
  "relationship": "Father", "student_id": 9
}'
```

**Add a timetable period**
```bash
curl -X POST $API/timetable "${H[@]}" -d '{
  "class_id": 7, "subject_id": 1, "teacher_id": 7,
  "day_of_week": "Monday", "start_time": "09:00", "end_time": "09:45", "room_number": "201"
}'
```

**Mark today's attendance for the whole class**
```bash
curl -X POST $API/attendance/bulk "${H[@]}" -d '{
  "class_id": 7,
  "records": [
    {"student_id": 9,  "status": "Present"},
    {"student_id": 10, "status": "Late", "remarks": "Bus delay"}
  ]
}'
```

**Create an exam and enter marks** (grade calculated automatically)
```bash
curl -X POST $API/exams "${H[@]}" -d '{
  "exam_name": "Maths Mid-Term", "exam_type": "Mid-Term",
  "class_id": 7, "subject_id": 1, "exam_date": "2026-12-10",
  "total_marks": 100, "pass_marks": 35
}'
curl -X POST $API/marks "${H[@]}" -d '{"student_id": 9, "exam_id": 8, "marks_obtained": 84}'
# -> "grade": "A"
```

**Create a fee and take payments**
```bash
curl -X POST $API/fees "${H[@]}" -d '{
  "student_id": 9, "fee_type": "Tuition", "amount": 5000, "due_date": "2026-12-31"
}'                                                        # status: Unpaid
curl -X POST $API/fees/9/pay "${H[@]}" -d '{"amount": 2000}'   # status: Partial
curl -X POST $API/fees/9/pay "${H[@]}" -d '{"amount": 3000}'   # status: Paid
```

**Update only one field**
```bash
curl -X PATCH $API/students/9 "${H[@]}" -d '{"phone": "9222222222"}'
```

**Reports**
```bash
curl $API/dashboard "${H[@]}"
curl $API/students/9/profile "${H[@]}"
curl $API/students/9/report-card "${H[@]}"
curl "$API/classes/7/attendance?attend_date=2026-11-19" "${H[@]}"
curl $API/exams/8/results "${H[@]}"
curl "$API/fees/pending?overdue_only=true" "${H[@]}"
```

> The IDs (7, 9, 8…) are examples. Use the IDs returned by your own create requests.

---

## 9. Error codes

| Code | Meaning | Typical cause |
|---|---|---|
| 200 / 201 / 204 | Success | OK / created / deleted |
| 400 | Rule broken or related record missing | class full, marks > total, `class_id` doesn't exist |
| 401 | Not logged in | Missing/expired token, so log in and click **Authorize** again |
| 404 | Not found | Wrong ID in the URL |
| 409 | Duplicate or clash | Same email, same mark twice, timetable clash |
| 422 | Invalid input | Wrong type, `gender: "M"` instead of `"Male"`, bad date format |

Every error body explains the reason:
```json
{ "detail": "Grade 5A is full (40/40 students)" }
```

---

## 10. Project files

| File | What it contains |
|---|---|
| `main.py` | Creates the app and registers all routers |
| `database.py` | Neon connection (reads `DATABASE_URL` from `.env`) |
| `auth.py`, `models.py`, `schemas.py`, `security.py` | Login, registration, passwords ([README.md](README.md)) |
| `school_models.py` | Python classes mapped to the 12 school tables |
| `school_schemas.py` | Request/response formats and allowed values |
| `crud.py` | Shared list/get/create/update/delete logic for all tables |
| `school.py` | Business rules, reports and actions |
| `SCHOOL_MANAGEMENT.md` | This guide |

**Notes**
- The API **does not create or change tables**. It works with the tables you made in Neon. If you add a column in Neon, add it to `school_models.py` and `school_schemas.py` too.
- Any logged-in user can currently manage all school data. Before real use, add roles (for example admin, teacher and parent) to limit who can do what.
