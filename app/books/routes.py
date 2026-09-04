import requests
from datetime import date, datetime
from flask import render_template, request, redirect, url_for, jsonify, current_app

from . import books_bp
from app.models import db, Book, ReadingLog

GOOGLE_BOOKS_API = "https://www.googleapis.com/books/v1/volumes"


@books_bp.route("/search-books")
def search_api():
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
        })

    return jsonify(results)


@books_bp.route("/add-book", methods=["POST"])
def add_book():
    """Add a book found via search onto the child's shelf."""
    google_books_id = request.form.get("google_books_id")

    existing = Book.query.filter_by(google_books_id=google_books_id).first()
    if existing:
        return redirect(url_for("books.detail", book_id=existing.id))

    status = request.form.get("status", "want_to_read")
    if status not in {"want_to_read", "reading", "finished"}:
        status = "want_to_read"

    book = Book(
        google_books_id=google_books_id,
        title=request.form.get("title"),
        author=request.form.get("author"),
        cover_url=request.form.get("cover_url"),
        status=status,
    )
    db.session.add(book)
    db.session.commit()

    return redirect(url_for("books.detail", book_id=book.id))


@books_bp.route("/<int:book_id>")
def detail(book_id):
    """Book detail page: status, times read, and the reading log history."""
    book = Book.query.get_or_404(book_id)

    return render_template(
        "book_detail.html",
        book=book,
        logs=book.logs,
        times_read=book.times_read,
        today=date.today(),
    )


@books_bp.route("/<int:book_id>/status", methods=["POST"])
def update_status(book_id):
    """Update a book's shelf status (want_to_read / reading / finished)."""
    book = Book.query.get_or_404(book_id)
    new_status = request.form.get("status")

    if new_status in {"want_to_read", "reading", "finished"}:
        book.status = new_status
        db.session.commit()

    return redirect(url_for("books.detail", book_id=book.id))


@books_bp.route("/<int:book_id>/log", methods=["POST"])
def log_reading(book_id):
    """Add a reading log entry: date read, star rating, optional review."""
    book = Book.query.get_or_404(book_id)

    date_read_str = request.form.get("date_read")
    if date_read_str:
        date_read = datetime.strptime(date_read_str, "%Y-%m-%d").date()
    else:
        date_read = date.today()

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
def delete_log(book_id, log_id):
    """Remove a single reading log entry from a book's history."""
    log = ReadingLog.query.filter_by(id=log_id, book_id=book_id).first_or_404()
    db.session.delete(log)
    db.session.commit()
    return redirect(url_for("books.detail", book_id=book_id))


@books_bp.route("/<int:book_id>/delete", methods=["POST"])
def delete_book(book_id):
    """Remove a book (and its reading logs) from the shelf entirely."""
    book = Book.query.get_or_404(book_id)

    ReadingLog.query.filter_by(book_id=book.id).delete()
    db.session.delete(book)
    db.session.commit()

    return redirect(url_for("library.bookshelf"))