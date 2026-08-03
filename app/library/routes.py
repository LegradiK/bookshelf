from datetime import date, datetime
from flask import Blueprint, render_template, request, redirect, url_for
from app.extensions import db
from app.models import Book, ReadingLog, Setting

library_bp = Blueprint("library", __name__)


@library_bp.route("/")
def bookshelf():
    status = request.args.get("status", "all")
    query = Book.query
    if status in ("want_to_read", "reading", "finished"):
        query = query.filter_by(status=status)
    books = query.order_by(Book.added_on.desc()).all()
    return render_template("bookshelf.html", books=books, active_status=status)


@library_bp.route("/search")
def search_page():
    return render_template("search_results.html")


@library_bp.route("/book/<int:book_id>")
def book_detail(book_id):
    book = Book.query.get_or_404(book_id)
    return render_template("book_detail.html", book=book, today=date.today().isoformat())


@library_bp.route("/book/<int:book_id>/log", methods=["POST"])
def log_reading(book_id):
    book = Book.query.get_or_404(book_id)

    date_str = request.form.get("date_read")
    try:
        date_read = datetime.strptime(date_str, "%Y-%m-%d").date() if date_str else date.today()
    except ValueError:
        date_read = date.today()

    stars_raw = request.form.get("stars")
    stars = int(stars_raw) if stars_raw else None
    review = request.form.get("review") or None

    log = ReadingLog(book_id=book.id, date_read=date_read, stars=stars, review=review)
    db.session.add(log)
    book.status = "finished"
    db.session.commit()

    return redirect(url_for("library.book_detail", book_id=book.id))


@library_bp.route("/book/<int:book_id>/status", methods=["POST"])
def update_status(book_id):
    book = Book.query.get_or_404(book_id)
    new_status = request.form.get("status")
    if new_status in ("want_to_read", "reading", "finished"):
        book.status = new_status
        db.session.commit()
    return redirect(url_for("library.book_detail", book_id=book.id))


@library_bp.route("/book/<int:book_id>/delete", methods=["POST"])
def delete_book(book_id):
    book = Book.query.get_or_404(book_id)
    db.session.delete(book)
    db.session.commit()
    return redirect(url_for("library.bookshelf"))


@library_bp.route("/theme", methods=["GET", "POST"])
def theme_picker():
    setting = Setting.get()
    if request.method == "POST":
        chosen = request.form.get("theme")
        if chosen in ("dragons", "unicorns"):
            setting.theme = chosen
            db.session.commit()
        return redirect(url_for("library.bookshelf"))
    return render_template("theme_picker.html", current_theme=setting.theme)
