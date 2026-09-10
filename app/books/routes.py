import requests
from dotenv import load_dotenv
from datetime import date, datetime
from flask import render_template, request, redirect, url_for, jsonify, current_app, session, abort

from . import books_bp
from app.models import db, Book, ReadingLog
from app.auth.routes import login_required

GOOGLE_BOOKS_API = "https://www.googleapis.com/books/v1/volumes"

load_dotenv('data.env')

@books_bp.route("/search-books")
def search_books():
    """AJAX endpoint: search Google Books and return simplified results for the search page."""
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify([])

    try:
        params = {"q": q, "maxResults": 30}
        api_key = current_app.config.get("GOOGLE_BOOKS_API_KEY")
        if api_key:
            params["key"] = api_key

        resp = requests.get(GOOGLE_BOOKS_API, params=params, timeout=5)
        resp.raise_for_status()
    except requests.exceptions.HTTPError as e:
        if e.response is not None and e.response.status_code == 429:
            return jsonify({"error": "Search is busy right now — wait a moment and try again."})
        return jsonify({"error": "Something went wrong searching. Try again."})
    except requests.exceptions.RequestException:
        return jsonify({"error": "Something went wrong searching. Try again."})

    items = resp.json().get("items", [])

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

    return jsonify(results)


def _extract_isbn(volume_info):
    """Pull ISBN-13 (preferred) or ISBN-10 out of Google Books' industryIdentifiers list."""
    identifiers = volume_info.get("industryIdentifiers", [])
    isbn_13 = next((i["identifier"] for i in identifiers if i.get("type") == "ISBN_13"), None)
    isbn_10 = next((i["identifier"] for i in identifiers if i.get("type") == "ISBN_10"), None)
    return isbn_13 or isbn_10


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


@books_bp.route("/add-book", methods=["POST"])
@login_required
def add_book():
    """Add a book found via search onto the child's shelf."""
    user_id = session["user_id"]
    google_books_id = request.form.get("google_books_id")

    existing = Book.query.filter_by(google_books_id=google_books_id, user_id=user_id).first()
    if existing:
        return redirect(url_for("books.detail", book_id=existing.id))

    status = request.form.get("status", "want_to_read")
    if status not in {"want_to_read", "reading", "finished"}:
        status = "want_to_read"

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
    )
    db.session.add(book)
    db.session.commit()

    return redirect(url_for("books.detail", book_id=book.id))


@books_bp.route("/<int:book_id>")
@login_required
def detail(book_id):
    """Book detail page: status, times read, and the reading log history."""
    book = Book.query.filter_by(id=book_id, user_id=session["user_id"]).first_or_404()

    return render_template(
        "book_detail.html",
        book=book,
        logs=book.logs,
        times_read=book.times_read,
        today=date.today(),
    )


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