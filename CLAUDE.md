# CLAUDE.md — autoroster

## Project Overview

**autoroster** converts screenshots of shift worker calendars into Google Calendar / iCloud events. The core workflow:

1. Accept a screenshot of a calendar/roster
2. Use Claude's vision API to extract shift data (dates, times, shift types)
3. Parse the extracted data into structured calendar events
4. Write events to the user's calendar via Google Calendar API or iCloud CalDAV

## Architecture

- **Language**: Python
- **Vision**: Anthropic Claude API (`anthropic`) — Claude's multimodal vision understands coloured cell backgrounds, varied fonts, and grid layouts without preprocessing. `Pillow` is retained for thumbnail generation.
- **Calendar integration**: Google Calendar API and iCloud via CalDAV
- **Web interface**: Flask
- **Hosting**: Vercel (serverless, via `api/index.py` + `vercel.json`)

## Development Setup

### Python Project Setup
```bash
# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
# or if using pyproject.toml:
pip install -e ".[dev]"
```

### Directory Structure
```
autoroster/
├── CLAUDE.md
├── README.md
├── pyproject.toml
├── requirements.txt
├── vercel.json              # Vercel deployment config
├── .gitignore
├── app.py                   # Flask application
├── api/
│   └── index.py             # Vercel entry point (imports app from app.py)
├── autoroster/              # main package
│   ├── __init__.py
│   ├── vision.py            # screenshot parsing via Claude vision
│   ├── parser.py            # structured data extraction
│   ├── auth/
│   │   ├── google.py
│   │   └── apple.py
│   └── calendar_clients/
│       ├── google_cal.py
│       └── icloud_cal.py
└── tests/
    ├── conftest.py
    ├── test_vision.py
    └── test_parser.py
```

## Coding Conventions

- Follow PEP 8; use `ruff` for linting and `black` for formatting
- Type hints on all function signatures
- Docstrings for public functions (Google style)
- Keep functions small and single-purpose
- Do not commit API keys or credentials — use environment variables or `.env` files (never committed)

## Key Workflows

### Running locally
```bash
flask run --port 5000
# or:
python app.py
```

### Running tests
```bash
pytest
# with coverage:
pytest --cov=autoroster
```

### Linting
```bash
ruff check .
black --check .
```

### Deploying to Vercel
```bash
vercel deploy
```

## Environment Variables

Set these in `.env` locally and in Vercel's project settings for production:

```
# Flask
SECRET_KEY=<random secret string>

# Anthropic — image parsing
ANTHROPIC_API_KEY=<your Anthropic API key>

# Google OAuth + Calendar
GOOGLE_CLIENT_ID=<...>
GOOGLE_CLIENT_SECRET=<...>
GOOGLE_REDIRECT_URI=https://<your-vercel-domain>/auth/google/callback
```

The Anthropic API key is the only cloud credential needed for image parsing.
Get one at https://console.anthropic.com.

## Vercel Notes

- `vercel.json` routes all requests to `api/index.py`, which re-exports the Flask `app`
- Vercel's Python runtime serves Flask via WSGI automatically
- Flask cookie-based sessions work fine across serverless invocations (client-side signed cookies)
- Max request body size on Vercel is 4.5 MB — sufficient for mobile screenshots
- Function timeout: 60 s (Pro) / 10 s (Hobby). The Claude API call typically completes in 3–8 s.
- `SECRET_KEY` must be set as a Vercel environment variable (not `os.urandom`) so cookies remain valid across cold starts

## Git Conventions

- Branch naming: `feature/description`, `fix/description`, `chore/description`
- Commit messages: imperative mood, present tense (e.g. "Add vision parser module")
- Keep commits focused and atomic
- Do not commit generated files, `.venv/`, `__pycache__/`, or `.env`

## Notes for AI Assistants

- **Vision**: Use the Anthropic Claude API (`anthropic` package) with `client.messages.parse()` and a Pydantic output schema for structured extraction. Model: `claude-opus-4-6`. Do not add Google Cloud Vision, pytesseract, opencv, or other OCR libraries.
- **No other AI APIs** — only the Anthropic API is used. Do not add OpenAI or other AI services.
- When adding dependencies, update both `pyproject.toml` and `requirements.txt`
- Tests should use `pytest` and mock the Anthropic client (`anthropic.Anthropic`)
- Do not over-engineer — this is a focused utility tool
