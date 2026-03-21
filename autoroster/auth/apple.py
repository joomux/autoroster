"""Apple Sign In authentication.

iCloud CalDAV does not support OAuth tokens. After signing in with Apple,
users must provide an app-specific password generated at appleid.apple.com
to grant access to their iCloud Calendar via CalDAV.
"""

import json
import os
import time
from urllib.parse import urlencode


def _is_allowed(email: str) -> bool:
    allowed = os.environ.get("ALLOWED_EMAILS", "")
    if not allowed:
        return True  # no restriction configured
    return email.lower() in {e.strip().lower() for e in allowed.split(",")}

import jwt
import requests
from flask import Blueprint, flash, redirect, render_template, request, session, url_for

apple_bp = Blueprint("apple_auth", __name__)

APPLE_AUTH_URL = "https://appleid.apple.com/auth/authorize"
APPLE_TOKEN_URL = "https://appleid.apple.com/auth/token"
APPLE_KEYS_URL = "https://appleid.apple.com/auth/keys"


def _generate_client_secret() -> str:
    """Generate a signed JWT to use as the Apple OAuth client_secret."""
    private_key = os.environ["APPLE_PRIVATE_KEY"].replace("\\n", "\n")
    headers = {"kid": os.environ["APPLE_KEY_ID"], "alg": "ES256"}
    now = int(time.time())
    payload = {
        "iss": os.environ["APPLE_TEAM_ID"],
        "iat": now,
        "exp": now + 86400 * 180,  # 6 months
        "aud": "https://appleid.apple.com",
        "sub": os.environ["APPLE_CLIENT_ID"],
    }
    return jwt.encode(payload, private_key, algorithm="ES256", headers=headers)


def _verify_identity_token(identity_token: str) -> dict:
    """Decode and verify an Apple identity token (JWT)."""
    resp = requests.get(APPLE_KEYS_URL, timeout=10)
    resp.raise_for_status()
    keys = resp.json()["keys"]

    unverified_header = jwt.get_unverified_header(identity_token)
    matching_key = next(
        (k for k in keys if k["kid"] == unverified_header["kid"]),
        None,
    )
    if matching_key is None:
        raise ValueError("Apple public key not found for this token.")

    public_key = jwt.algorithms.RSAAlgorithm.from_jwk(json.dumps(matching_key))
    payload = jwt.decode(
        identity_token,
        public_key,
        algorithms=["RS256"],
        audience=os.environ["APPLE_CLIENT_ID"],
    )
    return payload


@apple_bp.route("/login")
def login():
    flash(
        "Not implemented yet because Apple want to charge me $99/year and that's crazy. Just use Google instead.",
        "error",
    )
    return redirect(url_for("login"))


@apple_bp.route("/callback", methods=["POST"])
def callback():
    error = request.form.get("error")
    if error:
        flash(f"Apple sign-in failed: {error}", "error")
        return redirect(url_for("login"))

    state = request.form.get("state")
    if state != session.pop("apple_oauth_state", None):
        flash("Invalid state parameter — possible CSRF.", "error")
        return redirect(url_for("login"))

    code = request.form.get("code")
    identity_token = request.form.get("id_token")

    # Optionally decode the name from the first-time response
    user_json = request.form.get("user")
    name = ""
    email = ""
    if user_json:
        user_data = json.loads(user_json)
        name_parts = user_data.get("name", {})
        name = f"{name_parts.get('firstName', '')} {name_parts.get('lastName', '')}".strip()
        email = user_data.get("email", "")

    # Verify identity token to get the stable sub and email
    try:
        claims = _verify_identity_token(identity_token)
    except Exception as exc:
        flash(f"Could not verify Apple identity: {exc}", "error")
        return redirect(url_for("login"))

    if not email:
        email = claims.get("email", "")

    if not _is_allowed(email):
        session.clear()
        flash("This Apple account is not authorised to use autoroster.", "error")
        return redirect(url_for("login"))

    session["user"] = {
        "provider": "apple",
        "sub": claims["sub"],
        "email": email,
        "name": name or email,
        "picture": "",
    }

    # Apple Sign In does not provide CalDAV credentials. Redirect the user
    # to the iCloud connect page to enter their app-specific password.
    return redirect(url_for("apple_auth.icloud_connect"))


@apple_bp.route("/icloud", methods=["GET", "POST"])
def icloud_connect():
    if "user" not in session or session["user"].get("provider") != "apple":
        return redirect(url_for("login"))

    if request.method == "POST":
        icloud_email = request.form.get("icloud_email", "").strip()
        app_password = request.form.get("app_password", "").strip()

        if not icloud_email or not app_password:
            flash("Both iCloud email and app-specific password are required.", "error")
            return redirect(request.url)

        # Verify credentials by attempting a CalDAV connection
        try:
            from autoroster.calendar_clients.icloud_cal import verify_credentials

            verify_credentials(icloud_email, app_password)
        except Exception as exc:
            flash(f"Could not connect to iCloud Calendar: {exc}", "error")
            return redirect(request.url)

        session["icloud_credentials"] = {
            "username": icloud_email,
            "password": app_password,
        }
        return redirect(url_for("upload"))

    prefill_email = session["user"].get("email", "")
    return render_template("icloud_connect.html", user=session["user"], prefill_email=prefill_email)
