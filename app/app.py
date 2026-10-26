import hmac
import os
import secrets
from functools import wraps

import pymysql
from flask import (Flask, abort, flash, g, redirect, render_template, request,
                   session, url_for)

import db
from grading import MAX_COURSEWORK, MAX_EXAM, compute_grade, gpa, parse_mark

app = Flask(__name__)
app.config.update(
    SECRET_KEY=os.environ.get("SECRET_KEY", ""),
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
)

ADMIN_USER = os.environ.get("ADMIN_USER", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")

if not app.config["SECRET_KEY"] or not ADMIN_PASSWORD:
    raise RuntimeError("SECRET_KEY and ADMIN_PASSWORD must be set")


def get_db():
    if "db" not in g:
        g.db = db.connect()
    return g.db


@app.teardown_appcontext
def close_db(_exc):
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


def query(sql, args=(), one=False):
    with get_db().cursor() as cur:
        cur.execute(sql, args)
        return cur.fetchone() if one else cur.fetchall()


def execute(sql, args=()):
    with get_db().cursor() as cur:
        cur.execute(sql, args)
        return cur.rowcount

def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user"):
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped


@app.before_request
def csrf_protect():
    if request.method == "POST":
        expected = session.get("csrf", "")
        sent = request.form.get("csrf_token", "")
        if not expected or not hmac.compare_digest(expected, sent):
            abort(400, "Invalid or missing CSRF token. Reload the page and try again.")


@app.context_processor
def inject_csrf():
    if "csrf" not in session:
        session["csrf"] = secrets.token_hex(16)
    return {"csrf_token": session["csrf"]}


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user_ok = hmac.compare_digest(request.form.get("username", "").encode(),
                                      ADMIN_USER.encode())
        pass_ok = hmac.compare_digest(request.form.get("password", "").encode(),
                                      ADMIN_PASSWORD.encode())
        if user_ok and pass_ok:
            session.clear()
            session["user"] = ADMIN_USER
            return redirect(url_for("index"))
        flash("Invalid username or password.", "error")
    return render_template("login.html")


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/")
@login_required
def index():
    counts = query(
        "SELECT (SELECT COUNT(*) FROM students) AS students,"
        " (SELECT COUNT(*) FROM courses) AS courses,"
        " (SELECT COUNT(*) FROM results) AS results",
        one=True,
    )
    return render_template("index.html", counts=counts)


@app.route("/students", methods=["GET", "POST"])
@login_required
def students():
    if request.method == "POST":
        reg_no = request.form.get("reg_no", "").strip()
        full_name = request.form.get("full_name", "").strip()
        programme = request.form.get("programme", "").strip()
        if not (reg_no and full_name and programme):
            flash("All student fields are required.", "error")
        elif len(reg_no) > 30 or len(full_name) > 120 or len(programme) > 120:
            flash("One of the values is too long.", "error")
        else:
            try:
                execute(
                    "INSERT INTO students (reg_no, full_name, programme) VALUES (%s, %s, %s)",
                    (reg_no, full_name, programme),
                )
                flash(f"Added student {full_name}.", "ok")
            except pymysql.err.IntegrityError:
                flash("A student with that registration number already exists.", "error")
        return redirect(url_for("students"))

    rows = query("SELECT id, reg_no, full_name, programme FROM students ORDER BY reg_no")
    return render_template("students.html", students=rows)


@app.route("/students/<int:student_id>")
@login_required
def student_detail(student_id):
    student = query("SELECT id, reg_no, full_name, programme FROM students WHERE id = %s",
                    (student_id,), one=True)
    if student is None:
        abort(404)
    rows = query(
        "SELECT c.code, c.title, c.credit_units, r.coursework, r.exam, r.total,"
        " r.grade, r.grade_point"
        " FROM results r JOIN courses c ON c.id = r.course_id"
        " WHERE r.student_id = %s ORDER BY c.code",
        (student_id,),
    )
    return render_template(
        "student_detail.html",
        student=student,
        rows=rows,
        gpa=gpa(rows),
        total_units=sum(r["credit_units"] for r in rows),
    )


@app.route("/students/<int:student_id>/delete", methods=["POST"])
@login_required
def delete_student(student_id):
    if execute("DELETE FROM students WHERE id = %s", (student_id,)):
        flash("Student and their results deleted.", "ok")
    return redirect(url_for("students"))


@app.route("/courses", methods=["GET", "POST"])
@login_required
def courses():
    if request.method == "POST":
        code = request.form.get("code", "").strip().upper()
        title = request.form.get("title", "").strip()
        credit_units = request.form.get("credit_units", type=int)
        if not (code and title):
            flash("Course code and title are required.", "error")
        elif credit_units is None or not 1 <= credit_units <= 20:
            flash("Credit units must be a whole number from 1 to 20.", "error")
        elif len(code) > 20 or len(title) > 150:
            flash("One of the values is too long.", "error")
        else:
            try:
                execute(
                    "INSERT INTO courses (code, title, credit_units) VALUES (%s, %s, %s)",
                    (code, title, credit_units),
                )
                flash(f"Added course {code}.", "ok")
            except pymysql.err.IntegrityError:
                flash("A course with that code already exists.", "error")
        return redirect(url_for("courses"))

    rows = query("SELECT id, code, title, credit_units FROM courses ORDER BY code")
    return render_template("courses.html", courses=rows)


@app.route("/courses/<int:course_id>/delete", methods=["POST"])
@login_required
def delete_course(course_id):
    if execute("DELETE FROM courses WHERE id = %s", (course_id,)):
        flash("Course and its results deleted.", "ok")
    return redirect(url_for("courses"))


@app.route("/results", methods=["GET", "POST"])
@login_required
def results():
    if request.method == "POST":
        student_id = request.form.get("student_id", type=int)
        course_id = request.form.get("course_id", type=int)
        if student_id is None or course_id is None:
            flash("Choose a student and a course.", "error")
            return redirect(url_for("results"))
        try:
            coursework = parse_mark(request.form.get("coursework"), MAX_COURSEWORK, "Coursework")
            exam = parse_mark(request.form.get("exam"), MAX_EXAM, "Exam")
        except ValueError as exc:
            flash(str(exc), "error")
            return redirect(url_for("results"))

        total = coursework + exam
        grade, grade_point = compute_grade(total)
        try:
           
            execute(
                "INSERT INTO results (student_id, course_id, coursework, exam, total,"
                " grade, grade_point) VALUES (%s, %s, %s, %s, %s, %s, %s)"
                " ON DUPLICATE KEY UPDATE coursework = VALUES(coursework),"
                " exam = VALUES(exam), total = VALUES(total), grade = VALUES(grade),"
                " grade_point = VALUES(grade_point)",
                (student_id, course_id, coursework, exam, total, grade, grade_point),
            )
            flash(f"Saved result: {total} ({grade}).", "ok")
        except pymysql.err.IntegrityError:
            flash("Unknown student or course.", "error")
        return redirect(url_for("results"))

    course_filter = request.args.get("course", type=int)
    sql = (
        "SELECT r.id, s.reg_no, s.full_name, c.code, c.title, r.coursework, r.exam,"
        " r.total, r.grade"
        " FROM results r JOIN students s ON s.id = r.student_id"
        " JOIN courses c ON c.id = r.course_id"
    )
    args = ()
    if course_filter:
        sql += " WHERE r.course_id = %s"
        args = (course_filter,)
    sql += " ORDER BY c.code, s.reg_no"

    return render_template(
        "results.html",
        rows=query(sql, args),
        students=query("SELECT id, reg_no, full_name FROM students ORDER BY reg_no"),
        courses=query("SELECT id, code, title FROM courses ORDER BY code"),
        course_filter=course_filter,
        max_coursework=MAX_COURSEWORK,
        max_exam=MAX_EXAM,
    )


@app.route("/results/<int:result_id>/delete", methods=["POST"])
@login_required
def delete_result(result_id):
    if execute("DELETE FROM results WHERE id = %s", (result_id,)):
        flash("Result deleted.", "ok")
    return redirect(url_for("results"))
