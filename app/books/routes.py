import requests
from flask import Blueprint, request, jsonify, redirect, url_for
from app.extensions import db
from app.models import Book

books_bp = Blueprint("books", __name__)

GOOGLE_BOOKS_API = "https://www.googleapis.com/books/v1/volumes"


@books_bp.route("/search-books")
def search_books():
    query = request.args.get("q", "").strip()
    if not query:
        return jsonify([])

    try:
        resp = requests.get(
            GOOGLE_BOOKS_API,
            params={"q": f"{query} subject:juvenile", "maxResults": 8},
            timeout=6,
        )
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException:
        return jsonify({"error": "Could not reach the book search service right now."}), 502

    results = []
    for item in data.get("items", []):
        info = item.get("volumeInfo", {})
        image_links = info.get("imageLinks", {})
        cover_url = image_links.get("thumbnail") or image_links.get("smallThumbnail")
        if cover_url:
            cover_url = cover_url.replace("http://", "https://")

        results.append({
            "google_books_id": item.get("id"),
            "title": info.get("title", "Untitled"),
            "author": ", ".join(info.get("authors", [])) or "Unknown author",
            "year": (info.get("publishedDate") or "")[:4],
            "cover_url": cover_url,
        })

    return jsonify(results)


@books_bp.route("/add-book", methods=["POST"])
def add_book():
    google_books_id = request.form.get("google_books_id")
    title = request.form.get("title")
    author = request.form.get("author")
    cover_url = request.form.get("cover_url")
    status = request.form.get("status", "want_to_read")

    existing = Book.query.filter_by(google_books_id=google_books_id).first() if google_books_id else None

    if existing:
        book = existing
        if status == "finished" and book.status != "finished":
            book.status = status
    else:
        book = Book(
            title=title,
            author=author,
            cover_url=cover_url,
            google_books_id=google_books_id,
            status=status,
        )
        db.session.add(book)

    db.session.commit()
    return redirect(url_for("library.book_detail", book_id=book.id))
