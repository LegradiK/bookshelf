# My Bookshelf — reading tracker

A small Flask website for a child to track what they've read: search and add books
(with cover art pulled automatically from Google Books), log each time they read a
book with a star rating and a written review, keep a want-to-read list, and pick
between two themes (dragons and knights / princesses and unicorns).

## Setup

```bash
python -m venv venv
source venv/bin/activate      # on Windows: venv\Scripts\activate
pip install -r requirements.txt
python run.py
```

Then open http://127.0.0.1:5000 in a browser.

The first time you run it, it'll create a SQLite database at
`instance/reading_tracker.db` automatically — no manual setup needed.

## How it works

- **`/`** — the bookshelf, with tabs to filter by "reading now", "finished", and
  "want to read"
- **`/search`** — search Google Books and add a result straight to the shelf
- **`/book/<id>`** — a book's page: change its status, log a reading (date, stars,
  review), see the full reading history, or remove it
- **`/theme`** — switch between the two visual themes at any time

## Project structure

```
reading-tracker/
├── app/
│   ├── __init__.py        # app factory
│   ├── models.py           # Book, ReadingLog, Setting
│   ├── extensions.py       # SQLAlchemy instance
│   ├── books/routes.py     # book search (Google Books API) + add-book
│   ├── library/routes.py   # bookshelf, book detail, logging, theme picker
│   ├── static/css/style.css
│   ├── static/js/app.js    # debounced search box
│   └── templates/
├── config.py
├── run.py
└── requirements.txt
```

## Notes for next steps

- Currently single-shelf (one child). If you want multiple children/profiles later,
  add a `Child` model and a `child_id` foreign key on `Book`.
- If a book isn't in Google Books, there's currently no manual "add by hand" fallback
  — worth adding a plain form for that later.
- No authentication — fine for a private home network, but add a password/PIN
  gate before deploying anywhere public.
