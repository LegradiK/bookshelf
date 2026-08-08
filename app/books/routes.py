import requests
from datetime import date
from flask import render_template, request, redirect, url_for, jsonify

from . import books_bp
from app.models import db, Book, ReadingLog, Setting

GOOGLE_BOOKS_API = "https://www.googleapis.com/books/v1/volumes"


@books_bp.route("/search/api")
def search_api():
    """AJAX endpoint: search Google Books and return simplified results for the search page."""
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify([])

    resp = requests.get(GOOGLE_BOOKS_API, params={"q": q, "maxResults": 12}, timeout=5)
    resp.raise_for_status()
    items = resp.json().get("items", [])

    results = []
    for item in items:
        info = item.get("volumeInfo", {})
        image_links = info.get("imageLinks", {})
        results.append({
            "google_books_id": item.get("id"),
            "title": info.get("title", "Untitled"),
            "authors": ", ".join(info.get("authors", [])) or "Unknown author",
            "cover_url": image_links.get("thumbnail"),
        })

    return jsonify(results)


@books_bp.route("/add", methods=["POST"])
def add_book():
    """Add a book found via search onto the child's shelf (default status: want_to_read)."""
    google_books_id = request.form.get("google_books_id")

    existing = Book.query.filter_by(google_books_id=google_books_id).first()
    if existing:
        return redirect(url_for("books.detail", book_id=existing.id))

    book = Book(
        google_books_id=google_books_id,
        title=request.form.get("title"),
        author=request.form.get("authors"),
        cover_url=request.form.get("cover_url"),
        status="want_to_read",
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
        today=date.today().isoformat(),
        current_theme=Setting.get().theme,
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

    log = ReadingLog(
        book_id=book.id,
        date_read=request.form.get("date_read") or date.today(),
        stars=int(request.form.get("stars", 0)),
        review=request.form.get("review", "").strip(),
    )
    db.session.add(log)

    if book.status != "finished":
        book.status = "finished"

    db.session.commit()
    return redirect(url_for("books.detail", book_id=book.id))


@books_bp.route("/<int:book_id>/delete", methods=["POST"])
def delete_book(book_id):
    """Remove a book (and its reading logs) from the shelf entirely."""
    book = Book.query.get_or_404(book_id)

    ReadingLog.query.filter_by(book_id=book.id).delete()
    db.session.delete(book)
    db.session.commit()

    return redirect(url_for("library.bookshelf"))