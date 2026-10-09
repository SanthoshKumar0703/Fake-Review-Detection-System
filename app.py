"""
Fake Review Detection System
=============================
Flask backend serving a full web app: landing page, auth, dashboard,
single/bulk review analysis, searchable report history, and CSV/PDF export.

Run:
    python app.py
Then open http://127.0.0.1:5000 in your browser.
"""
import csv
import io
import os
import secrets
import sqlite3
import threading
import webbrowser
from datetime import datetime, timedelta
from functools import wraps

from flask import (
    Flask, render_template, request, redirect, url_for,
    session, flash, jsonify, send_file, g
)
from werkzeug.security import generate_password_hash, check_password_hash
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

from model.detect import analyze_review

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "instance", "app.db")

app = Flask(__name__)
app.secret_key = "dev-secret-key-change-this-in-production"

# ---------------------------------------------------------------------------
# Google OAuth config
# ---------------------------------------------------------------------------
# Get these from https://console.cloud.google.com/apis/credentials
# (create an "OAuth client ID" of type "Web application" and add
#  http://127.0.0.1:5000/login/google/callback as an authorized redirect URI).
# Easiest way to set them: real environment variables before running the app,
# e.g. on Windows PowerShell:
#   $env:GOOGLE_CLIENT_ID="your-client-id"
#   $env:GOOGLE_CLIENT_SECRET="your-client-secret"
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")

oauth = None
if GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET:
    from authlib.integrations.flask_client import OAuth

    oauth = OAuth(app)
    oauth.register(
        name="google",
        client_id=GOOGLE_CLIENT_ID,
        client_secret=GOOGLE_CLIENT_SECRET,
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        client_kwargs={"scope": "openid email profile"},
    )

# Used to sign password-reset tokens (separate salt, same secret key).
reset_serializer = URLSafeTimedSerializer(app.secret_key, salt="password-reset")
RESET_TOKEN_MAX_AGE = 60 * 30  # 30 minutes


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------
def get_db():
    if "db" not in g:
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            review_text TEXT NOT NULL,
            source TEXT NOT NULL DEFAULT 'manual',
            prediction TEXT NOT NULL,
            confidence REAL NOT NULL,
            suspicious_keywords TEXT NOT NULL DEFAULT '',
            word_count INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (id)
        );
        """
    )
    # Lightweight migration: add auth_provider column for accounts created
    # via Google sign-in, if it isn't there yet (older DB files won't have it).
    existing_cols = {row[1] for row in conn.execute("PRAGMA table_info(users)").fetchall()}
    if "auth_provider" not in existing_cols:
        conn.execute("ALTER TABLE users ADD COLUMN auth_provider TEXT NOT NULL DEFAULT 'local'")
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------
def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            flash("Please log in to continue.", "error")
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped


@app.context_processor
def inject_user():
    return {
        "current_username": session.get("username"),
        "is_logged_in": bool(session.get("user_id")),
    }


# ---------------------------------------------------------------------------
# Public pages
# ---------------------------------------------------------------------------
@app.route("/")
def home():
    return render_template("home.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not username or not email or not password:
            flash("All fields are required.", "error")
            return render_template("register.html")

        if len(password) < 6:
            flash("Password must be at least 6 characters.", "error")
            return render_template("register.html")

        db = get_db()
        try:
            cur = db.execute(
                "INSERT INTO users (username, email, password_hash, created_at, auth_provider) VALUES (?, ?, ?, ?, 'local')",
                (username, email, generate_password_hash(password), datetime.utcnow().isoformat()),
            )
            db.commit()
        except sqlite3.IntegrityError:
            flash("That username or email is already registered.", "error")
            return render_template("register.html")

        # Log the new user straight in and take them into the app instead of
        # bouncing them back to the sign-in page.
        session.clear()
        session["user_id"] = cur.lastrowid
        session["username"] = username
        flash(f"Welcome, {username}! Your account is ready.", "success")
        return redirect(url_for("dashboard"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        identifier = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        db = get_db()
        user = db.execute(
            "SELECT * FROM users WHERE username = ? OR email = ?", (identifier, identifier.lower())
        ).fetchone()

        if user is None or not check_password_hash(user["password_hash"], password):
            flash("Invalid username or password.", "error")
            return render_template("login.html")

        session.clear()
        session["user_id"] = user["id"]
        session["username"] = user["username"]
        flash(f"Welcome back, {user['username']}!", "success")
        return redirect(url_for("dashboard"))

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("home"))


# ---------------------------------------------------------------------------
# Forgot / reset password
# ---------------------------------------------------------------------------
@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    reset_link = None
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        db = get_db()
        user = db.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()

        # Always show the same message whether or not the account exists,
        # so the form can't be used to find out which emails are registered.
        flash("If that email is registered, a reset link has been generated below.", "success")

        if user is not None:
            token = reset_serializer.dumps({"uid": user["id"]})
            reset_link = url_for("reset_password", token=token, _external=True)
            # NOTE: no email service is wired up yet, so for now the link is
            # shown directly on the page. To send it by email instead, plug
            # in Flask-Mail (or any SMTP/API service) here and email
            # `reset_link` to the user rather than rendering it.

    return render_template("forgot_password.html", reset_link=reset_link)


@app.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):
    try:
        data = reset_serializer.loads(token, max_age=RESET_TOKEN_MAX_AGE)
    except SignatureExpired:
        flash("That reset link has expired. Please request a new one.", "error")
        return redirect(url_for("forgot_password"))
    except BadSignature:
        flash("That reset link is invalid.", "error")
        return redirect(url_for("forgot_password"))

    db = get_db()
    user = db.execute("SELECT * FROM users WHERE id=?", (data["uid"],)).fetchone()
    if user is None:
        flash("That account no longer exists.", "error")
        return redirect(url_for("forgot_password"))

    if request.method == "POST":
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")

        if len(password) < 6:
            flash("Password must be at least 6 characters.", "error")
            return render_template("reset_password.html", token=token)
        if password != confirm:
            flash("Passwords do not match.", "error")
            return render_template("reset_password.html", token=token)

        db.execute(
            "UPDATE users SET password_hash=? WHERE id=?",
            (generate_password_hash(password), user["id"]),
        )
        db.commit()
        flash("Your password has been reset. Please sign in.", "success")
        return redirect(url_for("login"))

    return render_template("reset_password.html", token=token)


# ---------------------------------------------------------------------------
# Google sign-in
# ---------------------------------------------------------------------------
@app.route("/login/google")
def google_login():
    if oauth is None:
        flash("Google sign-in isn't configured yet. Add GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET to enable it.", "error")
        return redirect(url_for("login"))
    redirect_uri = url_for("google_callback", _external=True)
    return oauth.google.authorize_redirect(redirect_uri)


@app.route("/login/google/callback")
def google_callback():
    if oauth is None:
        flash("Google sign-in isn't configured yet.", "error")
        return redirect(url_for("login"))

    token = oauth.google.authorize_access_token()
    userinfo = token.get("userinfo") or oauth.google.parse_id_token(token)
    email = (userinfo.get("email") or "").strip().lower()
    name = userinfo.get("name") or email.split("@")[0]

    if not email:
        flash("Google didn't return an email address, so we couldn't sign you in.", "error")
        return redirect(url_for("login"))

    db = get_db()
    user = db.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()

    if user is None:
        # First time signing in with this Google account: create one.
        username = _unique_username_from(db, name)
        placeholder_hash = generate_password_hash(secrets.token_hex(16))
        cur = db.execute(
            "INSERT INTO users (username, email, password_hash, created_at, auth_provider) VALUES (?, ?, ?, ?, 'google')",
            (username, email, placeholder_hash, datetime.utcnow().isoformat()),
        )
        db.commit()
        user_id, username = cur.lastrowid, username
    else:
        user_id, username = user["id"], user["username"]

    session.clear()
    session["user_id"] = user_id
    session["username"] = username
    flash(f"Welcome, {username}!", "success")
    return redirect(url_for("dashboard"))


def _unique_username_from(db, base_name):
    """Turn a Google display name into a free, DB-safe username."""
    base = "".join(c for c in base_name.lower().replace(" ", "_") if c.isalnum() or c == "_") or "agent"
    candidate = base
    n = 1
    while db.execute("SELECT 1 FROM users WHERE username=?", (candidate,)).fetchone():
        n += 1
        candidate = f"{base}{n}"
    return candidate


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------
@app.route("/dashboard")
@login_required
def dashboard():
    db = get_db()
    uid = session["user_id"]

    total = db.execute("SELECT COUNT(*) c FROM reviews WHERE user_id=?", (uid,)).fetchone()["c"]
    fake = db.execute("SELECT COUNT(*) c FROM reviews WHERE user_id=? AND prediction='fake'", (uid,)).fetchone()["c"]
    genuine = total - fake
    avg_conf_row = db.execute("SELECT AVG(confidence) a FROM reviews WHERE user_id=?", (uid,)).fetchone()
    avg_conf = round(avg_conf_row["a"], 1) if avg_conf_row["a"] else 0

    recent = db.execute(
        "SELECT * FROM reviews WHERE user_id=? ORDER BY created_at DESC LIMIT 8", (uid,)
    ).fetchall()

    return render_template(
        "dashboard.html",
        total=total, fake=fake, genuine=genuine, avg_conf=avg_conf, recent=recent,
    )


@app.route("/api/stats")
@login_required
def api_stats():
    db = get_db()
    uid = session["user_id"]

    days = []
    fake_series = []
    genuine_series = []
    for i in range(6, -1, -1):
        day = (datetime.utcnow() - timedelta(days=i)).strftime("%Y-%m-%d")
        days.append(day)
        f = db.execute(
            "SELECT COUNT(*) c FROM reviews WHERE user_id=? AND prediction='fake' AND date(created_at)=?",
            (uid, day),
        ).fetchone()["c"]
        gtotal = db.execute(
            "SELECT COUNT(*) c FROM reviews WHERE user_id=? AND date(created_at)=?",
            (uid, day),
        ).fetchone()["c"]
        fake_series.append(f)
        genuine_series.append(gtotal - f)

    total = db.execute("SELECT COUNT(*) c FROM reviews WHERE user_id=?", (uid,)).fetchone()["c"]
    fake = db.execute("SELECT COUNT(*) c FROM reviews WHERE user_id=? AND prediction='fake'", (uid,)).fetchone()["c"]

    return jsonify({
        "days": days,
        "fake_series": fake_series,
        "genuine_series": genuine_series,
        "ratio": {"fake": fake, "genuine": total - fake},
    })


# ---------------------------------------------------------------------------
# Analyze (single + bulk)
# ---------------------------------------------------------------------------
@app.route("/analyze", methods=["GET", "POST"])
@login_required
def analyze():
    result = None
    review_text = ""
    if request.method == "POST":
        review_text = request.form.get("review_text", "")
        result = analyze_review(review_text)

        db = get_db()
        db.execute(
            """INSERT INTO reviews
               (user_id, review_text, source, prediction, confidence, suspicious_keywords, word_count, created_at)
               VALUES (?, ?, 'manual', ?, ?, ?, ?, ?)""",
            (
                session["user_id"], review_text, result["prediction"], result["confidence"],
                " | ".join(result["suspicious_keywords"]), result["word_count"],
                datetime.utcnow().isoformat(),
            ),
        )
        db.commit()

    return render_template("analyze.html", result=result, review_text=review_text)


@app.route("/bulk-upload", methods=["POST"])
@login_required
def bulk_upload():
    file = request.files.get("csv_file")
    if not file or file.filename == "":
        flash("Please choose a CSV file to upload.", "error")
        return redirect(url_for("analyze"))

    if not file.filename.lower().endswith(".csv"):
        flash("Only .csv files are supported for bulk upload.", "error")
        return redirect(url_for("analyze"))

    stream = io.StringIO(file.stream.read().decode("utf-8-sig"), newline=None)
    reader = csv.reader(stream)
    rows = list(reader)

    if not rows:
        flash("The uploaded CSV appears to be empty.", "error")
        return redirect(url_for("analyze"))

    # Skip a header row if the first cell doesn't look like a review (short, no punctuation-ish text)
    header_candidates = {"review", "review_text", "text", "reviews"}
    start_idx = 1 if rows[0] and rows[0][0].strip().lower() in header_candidates else 0

    db = get_db()
    uid = session["user_id"]
    count = 0
    for row in rows[start_idx:]:
        if not row or not row[0].strip():
            continue
        text = row[0].strip()
        result = analyze_review(text)
        db.execute(
            """INSERT INTO reviews
               (user_id, review_text, source, prediction, confidence, suspicious_keywords, word_count, created_at)
               VALUES (?, ?, 'bulk', ?, ?, ?, ?, ?)""",
            (
                uid, text, result["prediction"], result["confidence"],
                " | ".join(result["suspicious_keywords"]), result["word_count"],
                datetime.utcnow().isoformat(),
            ),
        )
        count += 1
    db.commit()

    flash(f"Bulk analysis complete: {count} reviews processed.", "success")
    return redirect(url_for("reports"))


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------
@app.route("/reports")
@login_required
def reports():
    db = get_db()
    uid = session["user_id"]

    status = request.args.get("status", "all")
    q = request.args.get("q", "").strip()

    query = "SELECT * FROM reviews WHERE user_id=?"
    params = [uid]

    if status in ("fake", "genuine"):
        query += " AND prediction=?"
        params.append(status)

    if q:
        query += " AND review_text LIKE ?"
        params.append(f"%{q}%")

    query += " ORDER BY created_at DESC"
    rows = db.execute(query, params).fetchall()

    return render_template("reports.html", rows=rows, status=status, q=q)


def _filtered_rows():
    db = get_db()
    uid = session["user_id"]
    status = request.args.get("status", "all")
    q = request.args.get("q", "").strip()

    query = "SELECT * FROM reviews WHERE user_id=?"
    params = [uid]
    if status in ("fake", "genuine"):
        query += " AND prediction=?"
        params.append(status)
    if q:
        query += " AND review_text LIKE ?"
        params.append(f"%{q}%")
    query += " ORDER BY created_at DESC"
    return db.execute(query, params).fetchall()


@app.route("/export/csv")
@login_required
def export_csv():
    rows = _filtered_rows()
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["Review", "Prediction", "Confidence (%)", "Suspicious Signals", "Word Count", "Analyzed At"])
    for r in rows:
        writer.writerow([
            r["review_text"], r["prediction"], r["confidence"],
            r["suspicious_keywords"], r["word_count"], r["created_at"],
        ])
    mem = io.BytesIO(buf.getvalue().encode("utf-8"))
    return send_file(
        mem, mimetype="text/csv", as_attachment=True,
        download_name=f"review_report_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv",
    )


@app.route("/export/pdf")
@login_required
def export_pdf():
    from reportlab.lib.pagesizes import letter
    from reportlab.lib import colors
    from reportlab.lib.units import inch
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

    rows = _filtered_rows()
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter, topMargin=0.6 * inch, bottomMargin=0.6 * inch)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("TitleX", parent=styles["Title"], textColor=colors.HexColor("#12233B"))
    elements = [
        Paragraph("Fake Review Detection — Analysis Report", title_style),
        Paragraph(f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')} &nbsp;&nbsp; User: {session.get('username')}", styles["Normal"]),
        Spacer(1, 16),
    ]

    data = [["Review", "Verdict", "Confidence", "Words", "Date"]]
    body_style = ParagraphStyle("cell", parent=styles["Normal"], fontSize=8, leading=10)
    for r in rows:
        snippet = (r["review_text"][:110] + "…") if len(r["review_text"]) > 110 else r["review_text"]
        data.append([
            Paragraph(snippet, body_style),
            r["prediction"].upper(),
            f"{r['confidence']}%",
            str(r["word_count"]),
            r["created_at"][:10],
        ])

    table = Table(data, colWidths=[3.2 * inch, 0.9 * inch, 0.9 * inch, 0.6 * inch, 1 * inch], repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#12233B")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, 0), 9),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
        ("TOPPADDING", (0, 0), (-1, 0), 8),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D8DEE9")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F4F6FA")]),
    ]))
    elements.append(table)
    doc.build(elements)
    buf.seek(0)

    return send_file(
        buf, mimetype="application/pdf", as_attachment=True,
        download_name=f"review_report_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.pdf",
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def _open_browser():
    webbrowser.open("http://127.0.0.1:5000/")


if __name__ == "__main__":
    init_db()
    # Flask's debug reloader runs this file in two processes; only the real
    # worker process (not the reloader's parent) has WERKZEUG_RUN_MAIN set,
    # so this check stops the browser tab from opening twice.
    if os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        threading.Timer(1.0, _open_browser).start()
    app.run(debug=True)
else:
    init_db()
