from flask import Flask, request, render_template
import os, sqlite3, datetime, subprocess
from werkzeug.security import generate_password_hash, check_password_hash
from flask import session, redirect, url_for

app = Flask(__name__)
UPLOAD_FOLDER = "uploads"
app.secret_key = "qprint-secret-key"

ADMIN_PASSWORD_HASH = "scrypt:32768:8:1$MKAnYXLn3rJA7ojs$eca52d2425b38dee8c50e5a1e9d63f8262d3bd78acff937fccceed0de16921be67246dc7d66638d56e1e4e09c5d511f95310c026c22747e3633e5ff18f14b6d5"

UPI_ID = "yourupi@bank"
UPI_NAME = "NFSU Print Service"

# Ensure uploads folder exists
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)


@app.route("/")
def index():
    return render_template("index.html", upi_id=UPI_ID, upi_name=UPI_NAME)


@app.route("/print", methods=["POST"])
def print_file():
    # Get form data
    student_name = request.form["student_name"]
    course = request.form["course"]
    copies = int(request.form["copies"])
    pages_input = request.form["pages"]

    # Handle file upload
    file = request.files["file"]
    filepath = os.path.join(UPLOAD_FOLDER, file.filename)
    file.save(filepath)

    pages_printed = 0
    if pages_input:
        if "-" in pages_input:
            start, end = pages_input.split("-")
            pages_printed = int(end) - int(start) + 1
        else:
            pages_printed = int(pages_input)

    if pages_printed <= 0:
        pages_printed = 1

    cost = pages_printed * copies * 1


    if "pages_printed" in request.form and "total_cost" in request.form:
        try:
            pages_printed = int(request.form["pages_printed"])
            cost = int(request.form["total_cost"])
        except ValueError:
            pass  

    # Save to db
    conn = sqlite3.connect("logs.db")
    c = conn.cursor()

    # Generate next token number
    c.execute("SELECT MAX(token_number) FROM logs")
    last_token = c.fetchone()[0]
    token_number = 1 if last_token is None else last_token + 1

    c.execute("""
        INSERT INTO logs
        (student_name, course, filename, pages, copies, cost,
        timestamp, payment_status, token_number, print_status)
        VALUES (?,?,?,?,?,?,?,?,?,?)
    """, (
        student_name,
        course,
        file.filename,
        pages_printed,
        copies,
        cost,
        str(datetime.datetime.now()),
        "Pending",
        token_number,
        "Queued"
    ))
    conn.commit()
    conn.close()

    process_queue()

    return f"Print request submitted successfully. Your Token Number is {token_number}"

def process_queue():
    conn = sqlite3.connect("logs.db")
    c = conn.cursor()

    while True:
        c.execute("""
            SELECT id, filename, copies
            FROM logs
            WHERE print_status = 'Queued'
            ORDER BY token_number ASC
            LIMIT 1
        """)
        job = c.fetchone()

        if not job:
            break  # No more queued jobs

        job_id, filename, copies = job

        # Mark as Printing
        c.execute("UPDATE logs SET print_status='Printing' WHERE id=?", (job_id,))
        conn.commit()

        # Send to printer
        subprocess.run([
            "lp",
            "-d", "canon2925",
            "-n", str(copies),
            os.path.join(UPLOAD_FOLDER, filename)
        ])

        # Mark as Completed
        c.execute("UPDATE logs SET print_status='Completed' WHERE id=?", (job_id,))
        conn.commit()

    conn.close()

@app.route("/mark_paid/<int:log_id>")
def mark_paid(log_id):
    if not session.get("admin_logged_in"):
        return redirect("/admin_login")

    conn = sqlite3.connect("logs.db")
    c = conn.cursor()
    c.execute(
        "UPDATE logs SET payment_status = 'Paid' WHERE id = ?",
        (log_id,)
    )
    conn.commit()
    conn.close()
    return redirect("/admin")

@app.route("/admin")
def admin():
    if not session.get("admin_logged_in"):
        return redirect("/admin_login")

    status_filter = request.args.get("status")  # Paid / Pending / None

    conn = sqlite3.connect("logs.db")
    c = conn.cursor()

    # Apply filter if selected
    if status_filter in ["Paid", "Pending"]:
        c.execute(
            "SELECT * FROM logs WHERE payment_status = ? ORDER BY id DESC",
            (status_filter,)
        )
    else:
        c.execute("SELECT * FROM logs ORDER BY id DESC")

    rows = c.fetchall()

    # Daily summary (Paid only)
    c.execute("""
        SELECT 
            COUNT(*),
            SUM(pages * copies),
            SUM(cost)
        FROM logs
        WHERE DATE(timestamp) = DATE('now')
        AND payment_status = 'Paid'
    """)
    summary = c.fetchone()

    conn.close()

    total_jobs = summary[0] or 0
    total_pages = summary[1] or 0
    total_amount = summary[2] or 0

    return render_template(
        "admin.html",
        rows=rows,
        total_jobs=total_jobs,
        total_pages=total_pages,
        total_amount=total_amount,
        current_filter=status_filter
    )

import csv
from flask import Response

@app.route("/export_csv")
def export_csv():
    if not session.get("admin_logged_in"):
        return redirect("/admin_login")

    conn = sqlite3.connect("logs.db")
    c = conn.cursor()
    c.execute("""
        SELECT
            student_name,
            course,
            filename,
            pages,
            copies,
            cost,
            payment_status,
            timestamp
        FROM logs
        ORDER BY id DESC
    """)
    rows = c.fetchall()
    conn.close()

    def generate():
        # CSV header
        yield "Student Name,Course,File Name,Pages,Copies,Amount,Payment Status,Date & Time\n"

        # CSV rows
        for r in rows:
            yield f"{r[0]},{r[1]},{r[2]},{r[3]},{r[4]},{r[5]},{r[6]},{r[7]}\n"

    return Response(
        generate(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment;filename=print_logs.csv"}
    )

@app.route("/admin_login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        entered_pin = request.form.get("pin")

        if check_password_hash(ADMIN_PASSWORD_HASH, entered_pin):
            session["admin_logged_in"] = True
            return redirect("/admin")
        else:
            return render_template("admin_login.html", error="Invalid PIN")

    return render_template("admin_login.html")

@app.route("/admin_logout")
def admin_logout():
    session.pop("admin_logged_in", None)
    return redirect("/admin_login")

app.run(host="0.0.0.0", port=5000)
