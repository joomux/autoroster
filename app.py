import os
import tempfile
from functools import wraps

from dotenv import load_dotenv
from flask import Flask, flash, redirect, render_template, request, session, url_for

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", os.urandom(24).hex())
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16 MB

# ---------------------------------------------------------------------------
# Template filters
# ---------------------------------------------------------------------------

_MONTH_NAMES = [
    "", "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]


@app.template_filter("format_date")
def _filter_format_date(iso: str) -> str:
    from datetime import date

    d = date.fromisoformat(iso)
    return d.strftime("%a %-d %b %Y")


@app.template_filter("format_time")
def _filter_format_time(iso: str) -> str:
    from datetime import datetime

    dt = datetime.fromisoformat(iso)
    return dt.strftime("%-I:%M %p")


@app.context_processor
def _inject_month_name():
    def month_name(n):
        if n and 1 <= n <= 12:
            return _MONTH_NAMES[n]
        return ""

    return {"month_name": month_name}

from autoroster.auth.apple import apple_bp  # noqa: E402
from autoroster.auth.google import google_bp  # noqa: E402

app.register_blueprint(google_bp, url_prefix="/auth/google")
app.register_blueprint(apple_bp, url_prefix="/auth/apple")

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg"}


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)

    return decorated


def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route("/")
def index():
    if "user" in session:
        return redirect(url_for("upload"))
    return redirect(url_for("login"))


@app.route("/login")
def login():
    if "user" in session:
        return redirect(url_for("upload"))
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/upload", methods=["GET", "POST"])
@login_required
def upload():
    if request.method == "POST":
        if "screenshot" not in request.files:
            flash("No file selected.", "error")
            return redirect(request.url)

        file = request.files["screenshot"]
        if file.filename == "":
            flash("No file selected.", "error")
            return redirect(request.url)

        if not allowed_file(file.filename):
            flash("Please upload a PNG or JPG image.", "error")
            return redirect(request.url)

        month_hint = request.form.get("month", "").strip()
        year_hint = request.form.get("year", "").strip()
        month_int = int(month_hint) if month_hint.isdigit() and 1 <= int(month_hint) <= 12 else None
        year_int = int(year_hint) if year_hint.isdigit() and len(year_hint) == 4 else None

        suffix = "." + file.filename.rsplit(".", 1)[1].lower()
        tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
        try:
            file.save(tmp.name)
            tmp.close()

            from autoroster.parser import extract_events
            from autoroster.vision import parse_calendar_image

            raw = parse_calendar_image(tmp.name, month_hint=month_int, year_hint=year_int)
            events = extract_events(raw)
        except ValueError as exc:
            flash(str(exc), "error")
            return redirect(request.url)
        finally:
            os.unlink(tmp.name)

        if not events:
            flash(
                "No shift events found. Ensure the screenshot shows a roster with shift codes (A, N, P).",
                "error",
            )
            return redirect(request.url)

        session["pending_events"] = [e.to_dict() for e in events]
        session["roster_month"] = raw.get("month")
        session["roster_year"] = raw.get("year")
        return redirect(url_for("preview"))

    return render_template("upload.html", user=session["user"])


@app.route("/preview")
@login_required
def preview():
    events = session.get("pending_events")
    if not events:
        return redirect(url_for("upload"))

    provider = session["user"]["provider"]
    calendars = []
    try:
        calendars = _get_calendars(provider)
    except Exception as exc:
        flash(f"Could not load calendars: {exc}", "error")

    return render_template(
        "preview.html",
        events=events,
        calendars=calendars,
        user=session["user"],
        month=session.get("roster_month"),
        year=session.get("roster_year"),
    )


@app.route("/confirm", methods=["POST"])
@login_required
def confirm():
    events_data = session.get("pending_events")
    if not events_data:
        return redirect(url_for("upload"))

    calendar_id = request.form.get("calendar_id")
    if not calendar_id:
        flash("Please select a calendar.", "error")
        return redirect(url_for("preview"))

    provider = session["user"]["provider"]
    try:
        count = _write_events(events_data, calendar_id, provider)
        session.pop("pending_events", None)
        noun = "event" if count == 1 else "events"
        flash(f"Successfully added {count} shift {noun} to your calendar.", "success")
        return redirect(url_for("upload"))
    except Exception as exc:
        flash(f"Error writing events: {exc}", "error")
        return redirect(url_for("preview"))


def _get_calendars(provider: str) -> list:
    if provider == "google":
        from autoroster.calendar_clients.google_cal import get_calendars

        return get_calendars(session["credentials"])
    if provider == "apple":
        from autoroster.calendar_clients.icloud_cal import get_calendars

        return get_calendars(session["icloud_credentials"])
    return []


def _write_events(events_data: list, calendar_id: str, provider: str) -> int:
    from autoroster.parser import Event

    events = [Event.from_dict(e) for e in events_data]
    if provider == "google":
        from autoroster.calendar_clients.google_cal import create_events

        return create_events(session["credentials"], calendar_id, events)
    if provider == "apple":
        from autoroster.calendar_clients.icloud_cal import create_events

        return create_events(session["icloud_credentials"], calendar_id, events)
    return 0


if __name__ == "__main__":
    app.run(debug=True, port=5000)
