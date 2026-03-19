# CLAUDE.md — autoroster

## Project Overview

**autoroster** converts screenshots of shift worker calendars into Apple Calendar events. The core workflow:

1. Accept a screenshot of a calendar/roster
2. Use vision/OCR to extract shift data (dates, times, shift types)
3. Parse the extracted data into structured calendar events
4. Write events to Apple Calendar via native APIs or AppleScript

## Repository State

This project is in early initialization. Currently the repo contains only:
- `README.md` — project description
- `CLAUDE.md` — this file

No source code, dependencies, or tooling have been established yet.

## Intended Architecture

Given the project goals, the expected stack will likely include:

- **Language**: Python (best ecosystem for vision/OCR and calendar integration on macOS)
- **Vision/OCR**: Native Python libraries only — `Pillow` for image handling, `pytesseract` (Tesseract OCR) for text extraction, `opencv-python` for image preprocessing if needed
- **Calendar integration**: `EventKit` via PyObjC, or AppleScript via `subprocess`
- **CLI interface**: `click` or `argparse` for accepting screenshot paths

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

No external API keys or services are required. The tool runs entirely offline using local libraries.

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

- This is macOS-specific software — do not suggest Linux/Windows-only solutions for calendar integration
- **Do not use AI APIs or cloud services** — all image parsing must use native Python libraries (Pillow, pytesseract, opencv-python, etc.)
- When adding dependencies, update `pyproject.toml` or `requirements.txt` and document them
- Tests should use `pytest` and mock external calls (Apple Calendar)
- Do not over-engineer — this is a focused utility tool
