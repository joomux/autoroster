# CLAUDE.md — autoroster

## Project Overview

**autoroster** converts screenshots of shift worker calendars into Apple Calendar events. The core workflow:

1. Accept a screenshot of a calendar/roster
2. Use vision/OCR to extract shift data (dates, times, shift types)
3. Parse the extracted data into structured calendar events
4. Write events to Apple Calendar via native APIs or AppleScript

## Intended Architecture

- **Language**: Python
- **Vision/OCR**: Google Cloud Vision API (`google-cloud-vision`) — handles coloured cell backgrounds and varied fonts robustly. `Pillow` is retained for thumbnail generation.
- **Calendar integration**: Google Calendar API and iCloud via CalDAV
- **Web interface**: Flask

## Development Setup (to be established)

When setting up the project, follow these conventions:

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

### Expected Directory Structure
```
autoroster/
├── CLAUDE.md
├── README.md
├── pyproject.toml          # or requirements.txt
├── .gitignore
├── autoroster/             # main package
│   ├── __init__.py
│   ├── cli.py              # entry point / CLI
│   ├── vision.py           # screenshot parsing / OCR
│   ├── parser.py           # structured data extraction
│   └── calendar.py         # Apple Calendar integration
└── tests/
    ├── conftest.py
    ├── test_vision.py
    ├── test_parser.py
    └── test_calendar.py
```

## Coding Conventions

- Follow PEP 8; use `ruff` for linting and `black` for formatting
- Type hints on all function signatures
- Docstrings for public functions (Google style)
- Keep functions small and single-purpose
- Do not commit API keys or credentials — use environment variables or `.env` files (never committed)

## Key Workflows

### Running the tool (once implemented)
```bash
python -m autoroster path/to/screenshot.png
# or via CLI entry point:
autoroster path/to/screenshot.png
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

## Environment Variables

```
GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account-key.json
```

The Google Cloud Vision API is the only external service. It requires a service account key (see GCP setup below). Volume is always under 1,000 images/month so it stays within the free tier.

## Apple Calendar Integration

This runs on macOS only. Calendar write access requires:
- macOS 10.14+ Calendar permission granted to the terminal/app
- `EventKit` access via PyObjC (`pyobjc-framework-EventKit`) or AppleScript

When using AppleScript:
```python
import subprocess
subprocess.run(["osascript", "-e", applescript_string], check=True)
```

## Git Conventions

- Branch naming: `feature/description`, `fix/description`, `chore/description`
- Commit messages: imperative mood, present tense (e.g. "Add vision parser module")
- Keep commits focused and atomic
- Do not commit generated files, `.venv/`, `__pycache__/`, or `.env`

## Notes for AI Assistants

- **Vision/OCR**: Use Google Cloud Vision API (`google-cloud-vision`) for all image parsing. Do not add pytesseract, opencv, or other local OCR libraries — Vision handles coloured backgrounds and varied layouts that local OCR cannot.
- **No other cloud services** — Vision API is the only permitted external API. Do not add OpenAI, Anthropic, or any other AI API.
- When adding dependencies, update both `pyproject.toml` and `requirements.txt`
- Tests should use `pytest` and mock the Vision API client (`google.cloud.vision.ImageAnnotatorClient`)
- Do not over-engineer — this is a focused utility tool
