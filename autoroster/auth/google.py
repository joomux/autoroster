"""Google OAuth 2.0 authentication and token management."""

import base64
import hashlib
import os
import secrets

import requests
from flask import Blueprint, redirect, request, session, url_for
from google_auth_oauthlib.flow import Flow

google_bp = Blueprint("google_auth", __name__)


def _is_allowed(email: str) -> bool:
    allowed = os.environ.get("ALLOWED_EMAILS", "")
    if not allowed:
        return True  # no restriction configured
    return email.lower() in {e.strip().lower() for e in allowed.split(",")}


SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
    "https://www.googleapis.com/auth/calendar",
]


def _build_flow() -> Flow:
    client_config = {
        "web": {
            "client_id": os.environ["GOOGLE_CLIENT_ID"],
            "client_secret": os.environ["GOOGLE_CLIENT_SECRET"],
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [os.environ["GOOGLE_REDIRECT_URI"]],
        }
    }
    flow = Flow.from_client_config(
        client_config,
        scopes=SCOPES,
        redirect_uri=os.environ["GOOGLE_REDIRECT_URI"],
    )
    return flow


def _generate_pkce() -> tuple[str, str]:
    code_verifier = secrets.token_urlsafe(96)
    code_challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(code_verifier.encode()).digest())
        .rstrip(b"=")
        .decode()
    )
    return code_verifier, code_challenge


@google_bp.route("/login")
def login():
    flow = _build_flow()
    code_verifier, code_challenge = _generate_pkce()
    auth_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
        code_challenge=code_challenge,
        code_challenge_method="S256",
    )
    session["google_oauth_state"] = state
    session["code_verifier"] = code_verifier
    return redirect(auth_url)


@google_bp.route("/callback")
def callback():
    state = session.pop("google_oauth_state", None)
    if state is None or state != request.args.get("state"):
        return redirect(url_for("login"))

    code_verifier = session.pop("code_verifier", None)
    flow = _build_flow()
    authorization_response = request.url.replace("http://", "https://", 1)
    flow.fetch_token(authorization_response=authorization_response, code_verifier=code_verifier)

    creds = flow.credentials
    credentials_dict = {
        "token": creds.token,
        "refresh_token": creds.refresh_token,
        "token_uri": creds.token_uri,
        "client_id": creds.client_id,
        "client_secret": creds.client_secret,
        "scopes": list(creds.scopes or SCOPES),
    }
    session["credentials"] = credentials_dict

    # Fetch user profile
    resp = requests.get(
        "https://www.googleapis.com/oauth2/v2/userinfo",
        headers={"Authorization": f"Bearer {creds.token}"},
        timeout=10,
    )
    resp.raise_for_status()
    profile = resp.json()

    email = profile.get("email", "")
    if not _is_allowed(email):
        session.clear()
        from flask import flash
        flash("This Google account is not authorised to use autoroster.", "error")
        return redirect(url_for("login"))

    session["user"] = {
        "provider": "google",
        "email": email,
        "name": profile.get("name", email),
        "picture": profile.get("picture", ""),
    }

    return redirect(url_for("upload"))
