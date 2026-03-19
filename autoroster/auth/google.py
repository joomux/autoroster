"""Google OAuth 2.0 authentication and token management."""

import os

import requests
from flask import Blueprint, redirect, request, session, url_for
from google_auth_oauthlib.flow import Flow

google_bp = Blueprint("google_auth", __name__)

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


@google_bp.route("/login")
def login():
    flow = _build_flow()
    auth_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )
    session["google_oauth_state"] = state
    return redirect(auth_url)


@google_bp.route("/callback")
def callback():
    state = session.pop("google_oauth_state", None)
    if state is None or state != request.args.get("state"):
        return redirect(url_for("login"))

    flow = _build_flow()
    flow.fetch_token(authorization_response=request.url)

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

    session["user"] = {
        "provider": "google",
        "email": profile.get("email", ""),
        "name": profile.get("name", profile.get("email", "")),
        "picture": profile.get("picture", ""),
    }

    return redirect(url_for("upload"))
