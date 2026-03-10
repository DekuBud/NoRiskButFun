# Setup

## Virtual environment

```bash
python -m venv .venv
source .venv/bin/activate
```

## Install dependencies

```bash
pip install -r requirements.txt
```

## Environment variables

Copy the example file:

```bash
cp .env.example .env
```

Available variables:

- `DATABASE_URL` — defaults to `sqlite:///./noriskbutfun.db`
- `NEWS_PROVIDER` — defaults to `mock`
- `NEWS_API_KEY` — optional placeholder for future news integration

## Run locally

```bash
uvicorn app.main:app --reload
```

Then open:

```text
http://127.0.0.1:8000
```

## Notes

- SQLite is the default embedded database for version 1.
- `WeasyPrint` may require system libraries on Linux depending on the machine setup.
- The upload route expects one PDF with extractable text.
