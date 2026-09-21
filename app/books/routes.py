import requests
import os
from dotenv import load_dotenv
from datetime import date, datetime
from flask import render_template, flash, request, redirect, url_for, jsonify, current_app, session
from markupsafe import escape
from . import books_bp
from app.models import db, Book, ReadingLog, User
from app.auth.routes import login_required
from pathlib import Path

GOOGLE_BOOKS_LINK = "https://www.googleapis.com/books/v1/volumes"

load_dotenv(Path(__file__).resolve().parents[2] / "data.env")
GOOGLE_BOOKS_API_KEY = os.environ.get("GOOGLE_BOOKS_API_KEY")

@books_bp.route("/search-books")
def search_books():
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify({"items": [], "total_items": 0})

    start_index = request.args.get("start", 0, type=int)

    try:
        params = {"q": q, "maxResults": 40, "startIndex": start_index}
        api_key = current_app.config.get("GOOGLE_BOOKS_API_KEY")
        if api_key:
            params["key"] = api_key

        resp = requests.get(GOOGLE_BOOKS_LINK, params=params, timeout=5)
        resp.raise_for_status()
    except requests.exceptions.HTTPError as e:
        if e.response is not None and e.response.status_code == 429:
            return jsonify({"error": "Search is busy right now — wait a moment and try again."})
        return jsonify({"error": "Something went wrong searching. Try again."})
    except requests.exceptions.RequestException:
        return jsonify({"error": "Something went wrong searching. Try again."})

    data = resp.json()
    items = data.get("items", [])
    total_items = data.get("totalItems", 0)

    results = []
    for item in items:
        info = item.get("volumeInfo", {})
        image_links = info.get("imageLinks", {})
        published_date = info.get("publishedDate", "")
        results.append({
            "google_books_id": item.get("id"),
            "title": info.get("title", "Untitled"),
            "author": ", ".join(info.get("authors", [])) or "Unknown author",
            "year": published_date[:4] if published_date else None,
            "cover_url": image_links.get("thumbnail"),
            "isbn": _extract_isbn(info),
            "categories": ", ".join(info.get("categories", [])),
        })

    return jsonify({"items": results, "total_items": total_items})


def _extract_isbn(volume_info):
    """Pull ISBN-13 (preferred) or ISBN-10 out of Google Books' industryIdentifiers list."""
    identifiers = volume_info.get("industryIdentifiers", [])
    isbn_13 = next((i["identifier"] for i in identifiers if i.get("type") == "ISBN_13"), None)
    isbn_10 = next((i["identifier"] for i in identifiers if i.get("type") == "ISBN_10"), None)
    return isbn_13 or isbn_10

def _fetch_volume_details(google_books_id):
    """Fetch a single volume by ID — used when bulk-adding from search results."""
    params = {}
    api_key = current_app.config.get("GOOGLE_BOOKS_API_KEY")
    if api_key:
        params["key"] = api_key

    resp = requests.get(f"{GOOGLE_BOOKS_LINK}/{google_books_id}", params=params, timeout=5)
    resp.raise_for_status()
    info = resp.json().get("volumeInfo", {})
    image_links = info.get("imageLinks", {})

    return {
        "google_books_id": google_books_id,
        "title": info.get("title", "Untitled"),
        "author": ", ".join(info.get("authors", [])) or "Unknown author",
        "cover_url": image_links.get("thumbnail"),
        "isbn": _extract_isbn(info),
        "categories": ", ".join(info.get("categories", [])),
    }


# Subject strings that show up in Open Library data but aren't really genres.
_SUBJECT_NOISE = {"accelerated reader", "lexile", "large type books", "protected daisy"}

# Canonical genre whitelist, each mapped to keywords that might appear in
# Open Library's messier subject strings.
_GENRE_KEYWORDS = {
    "Fiction":                ["fiction"],
    "Military Fiction":       ["military fiction", "war stories", "military-fiction"],
    "Action":                 ["action"],
    "Nonfiction":              ["nonfiction", "non-fiction"],
    "Fantasy":                 ["fantasy"],
    "Science Fiction":         ["science fiction", "sci-fi", "sci fi"],
    "Mystery":                 ["mystery", "detective"],
    "Thriller":                ["thriller", "suspense"],
    "Horror":                  ["horror"],
    "Romance":                 ["romance", "love stories"],
    "Historical Fiction":      ["historical fiction", "historical"],
    "Young Adult":             ["young adult", "teen fiction", "juvenile fiction"],
    "Children's":              ["children's", "juvenile literature", "picture books"],
    "Biography":               ["biography", "biographical"],
    "Memoir":                  ["memoir", "autobiography"],
    "Poetry":                  ["poetry", "poems"],
    "Classics":                ["classic"],
    "Contemporary":            ["contemporary"],
    "Graphic Novels & Comics": ["graphic novel", "comic"],
    "Adventure":               ["adventure"],
    "Crime":                   ["crime"],
    "War":                     ["war"],
    "Self Help":               ["self-help", "self help"],
}

# More specific genres are checked before broad ones, so e.g. "Historical
# Fiction" is preferred over the generic "Fiction" match.
_GENRE_PRIORITY = [
    "Military Fiction", "Historical Fiction", 
    "Science Fiction", "Graphic Novels & Comics", "Self Help", "Mystery",
    "Thriller", "Horror", "Romance", "War", "Fantasy", "Adventure", "Action",
    "Crime", "Biography", "Memoir", "Poetry", "Classics", "Contemporary",
    "Young Adult", "Children's",
    "Nonfiction", "Fiction",
]


def map_to_known_genres(subjects, limit=5):
    """
    Match raw Open Library subject strings against the canonical genre
    whitelist using keyword matching. Returns only whitelisted genre names,
    deduplicated, most-specific first.
    """
    matched = set()

    for subject in subjects:
        subject_lower = subject.lower()
        for genre in _GENRE_PRIORITY:
            if genre in matched:
                continue
            if any(kw in subject_lower for kw in _GENRE_KEYWORDS[genre]):
                matched.add(genre)
                break

    ordered = [g for g in _GENRE_PRIORITY if g in matched]
    return ordered[:limit]


def get_genres_from_open_library(isbn, google_categories=None, limit=5):
    """
    Fetch genre tags for a book, preferring Open Library subjects, falling
    back to Google Books categories (also mapped through the same whitelist)
    if Open Library has nothing specific.
    """
    genres = []

    if isbn:
        headers = {"User-Agent": "ReadingTracker/1.0 (contact: you@example.com)"}
        try:
            edition_resp = requests.get(
                f"https://openlibrary.org/isbn/{isbn}.json", headers=headers, timeout=5
            )
            if edition_resp.status_code == 200:
                works = edition_resp.json().get("works", [])
                if works:
                    work_resp = requests.get(
                        f"https://openlibrary.org{works[0]['key']}.json",
                        headers=headers, timeout=5,
                    )
                    if work_resp.status_code == 200:
                        subjects = work_resp.json().get("subjects", [])
                        cleaned = [
                            s for s in subjects
                            if s.lower() not in _SUBJECT_NOISE
                            and ":" not in s and not any(c.isdigit() for c in s)
                        ]
                        genres = map_to_known_genres(cleaned, limit=limit)
        except requests.RequestException:
            pass

    # If Open Library gave nothing (or only the generic "Fiction"/"Nonfiction"),
    # try mapping Google Books' categories through the same whitelist.
    if (not genres or genres == ["Fiction"] or genres == ["Nonfiction"]) and google_categories:
        google_matches = map_to_known_genres([google_categories], limit=limit)
        if google_matches:
            genres = google_matches

    return genres

@books_bp.route("/book/<int:book_id>/genres", methods=["POST"])
@login_required
def update_genres(book_id):
    book = Book.query.filter_by(id=book_id, user_id=session["user_id"]).first_or_404()
    book.categories = request.form.get("categories", "").strip()
    db.session.commit()
    return redirect(url_for("books.detail", book_id=book_id))

@books_bp.route("/<int:book_id>/status", methods=["POST"])
@login_required
def update_status(book_id):
    """Update a book's shelf status (want_to_read / reading / finished)."""
    book = Book.query.filter_by(id=book_id, user_id=session["user_id"]).first_or_404()
    new_status = request.form.get("status")

    if new_status in {"want_to_read", "reading", "finished"}:
        book.status = new_status
        db.session.commit()

    return redirect(url_for("books.detail", book_id=book.id))

@books_bp.route("/add-book", methods=["POST"])
@login_required
def add_book():
    """Add a book found via search onto the child's shelf."""
    user_id = session["user_id"]
    google_books_id = request.form.get("google_books_id")

    existing = Book.query.filter_by(google_books_id=google_books_id, user_id=user_id).first()
    if existing:
        flash(f'"{existing.title}" by {existing.author} is already on your bookshelf.<br>'
              f'Read it again? Update the times read count on its page.', "info")
        return redirect(url_for("books.detail", book_id=existing.id))

    status = request.form.get("status", "want_to_read")
    if status not in {"want_to_read", "reading", "finished"}:
        status = "want_to_read"

    times_read = 1 if status == "finished" else 0

    isbn = request.form.get("isbn", "")
    google_categories = request.form.get("categories", "")
    genres = get_genres_from_open_library(isbn, google_categories=google_categories)
    categories = ", ".join(genres) if genres else google_categories

    book = Book(
        user_id=user_id,
        google_books_id=google_books_id,
        isbn=isbn,
        title=request.form.get("title"),
        author=request.form.get("author"),
        cover_url=request.form.get("cover_url"),
        status=status,
        categories=categories,
        times_read=times_read,
    )
    db.session.add(book)
    db.session.commit()

    return redirect(url_for("books.detail", book_id=book.id))

@books_bp.route("/add-books", methods=["POST"])
@login_required
def add_books():
    """Add multiple books selected via checkboxes on the search results page."""
    user_id = session["user_id"]
    google_books_ids = request.form.getlist("google_books_id")
    status = request.form.get("status", "want_to_read")
    if status not in {"want_to_read", "reading", "finished"}:
        status = "want_to_read"

    times_read = 1 if status == "finished" else 0

    skipped = 0
    duplicates = []
    reread_duplicates = []
    for google_books_id in google_books_ids:
        existing = Book.query.filter_by(google_books_id=google_books_id, user_id=user_id).first()
        if existing:
            if status == "finished":
                reread_duplicates.append(f"{existing.title} - {existing.author}")
            else:
                duplicates.append(f"{existing.title} - {existing.author}")
            continue  # already on this user's shelf — skip rather than duplicate

        try:
            details = _fetch_volume_details(google_books_id)
        except requests.RequestException:
            skipped += 1
            continue  # skip any book whose lookup fails, rather than failing the whole batch

        genres = get_genres_from_open_library(details["isbn"], google_categories=details["categories"])
        categories = ", ".join(genres) if genres else details["categories"]

        book = Book(
            user_id=user_id,
            google_books_id=details["google_books_id"],
            isbn=details["isbn"],
            title=details["title"],
            author=details["author"],
            cover_url=details["cover_url"],
            status=status,
            categories=categories,
            times_read=times_read,
        )
        db.session.add(book)

    db.session.commit()

    if duplicates:
        items = "".join(f"<li>{escape(d)}</li>" for d in duplicates)
        flash(
            f"Already on your bookshelf:<ul>{items}</ul>",
            "info",
        )
    if reread_duplicates:
        items = "".join(f"<li>{escape(d)}</li>" for d in reread_duplicates)
        flash(
            f"Already on your bookshelf (read it again? update times read on each book's page):<ul>{items}</ul>",
            "info",
        )
    if skipped:
        flash(f"{skipped} book(s) couldn't be added — try again in a moment.", "warning")

    return redirect(url_for("library.bookshelf"))

@books_bp.route("/<int:book_id>")
@login_required
def detail(book_id):
    """Book detail page: status, times read, and the reading log history."""
    user = User.query.get(session["user_id"])
    book = Book.query.filter_by(id=book_id, user_id=session["user_id"]).first_or_404()

    return render_template(
        "book_detail.html",
        book=book,
        logs=book.logs,
        times_read=book.times_read,
        today=date.today(),
        user_name=user.username if user else None
    )


@books_bp.route("/<int:book_id>/times-read", methods=["POST"])
@login_required
def update_times_read(book_id):
    """Set how many times this book has been read, entered directly by the user."""
    book = Book.query.filter_by(id=book_id, user_id=session["user_id"]).first_or_404()

    times_read = request.form.get("times_read", type=int)

    if book.status != 'finished':
        book.times_read = 0
    elif times_read is not None and times_read >= 1:
        book.times_read = times_read

    db.session.commit()

    return redirect(url_for("books.detail", book_id=book.id))


@books_bp.route("/<int:book_id>/log", methods=["POST"])
@login_required
def log_reading(book_id):
    """Add a reading log entry: date read, star rating, optional review."""
    book = Book.query.filter_by(id=book_id, user_id=session["user_id"]).first_or_404()

    date_read_str = request.form.get("date_read")
    date_read = datetime.strptime(date_read_str, "%Y-%m-%d").date() if date_read_str else date.today()

    log = ReadingLog(
        book_id=book.id,
        date_read=date_read,
        stars=int(request.form.get("stars", 0)),
        review=request.form.get("review", "").strip(),
    )
    db.session.add(log)

    if book.status != "finished":
        book.status = "finished"

    db.session.commit()
    return redirect(url_for("books.detail", book_id=book.id))


@books_bp.route("/<int:book_id>/log/<int:log_id>/delete", methods=["POST"])
@login_required
def delete_log(book_id, log_id):
    """Remove a single reading log entry from a book's history."""
    book = Book.query.filter_by(id=book_id, user_id=session["user_id"]).first_or_404()
    log = ReadingLog.query.filter_by(id=log_id, book_id=book.id).first_or_404()
    db.session.delete(log)
    db.session.commit()
    return redirect(url_for("books.detail", book_id=book_id))


@books_bp.route("/<int:book_id>/delete", methods=["POST"])
@login_required
def delete_book(book_id):
    """Remove a book (and its reading logs) from the shelf entirely."""
    book = Book.query.filter_by(id=book_id, user_id=session["user_id"]).first_or_404()

    ReadingLog.query.filter_by(book_id=book.id).delete()
    db.session.delete(book)
    db.session.commit()

    return redirect(url_for("library.bookshelf"))

@books_bp.route("/delete-books", methods=["POST"])
@login_required
def delete_books():
    """Remove multiple books (and their reading logs) selected via checkboxes."""
    user_id = session["user_id"]
    book_ids = request.form.getlist("book_id", type=int)

    if book_ids:
        books = Book.query.filter(
            Book.id.in_(book_ids), Book.user_id == user_id
        ).all()
        for book in books:
            ReadingLog.query.filter_by(book_id=book.id).delete()
            db.session.delete(book)
        db.session.commit()

    return redirect(url_for("library.bookshelf"))