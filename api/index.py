# Vercel serverless entry point — re-exports the Flask app object.
# Vercel's @vercel/python runtime detects `app` and serves it via WSGI.
from app import app  # noqa: F401
