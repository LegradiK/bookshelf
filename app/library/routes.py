from flask import render_template, request, redirect, url_for

from . import library_bp
from app.models import db, Book, Setting

VALID_THEMES = {"dragons", "unicorns"}


@library_bp.route("/")
def bookshelf():
    """Main page: shows all logged books, optionally filtered by status."""
    status_filter = request.args.get("status")

    query = Book.query
    if status_filter:
        query = query.filter_by(status=status_filter)

    books = query.order_by(Book.added_on.desc()).all()

    return render_template(
        "bookshelf.html",
        books=books,
        active_status=status_filter,
        current_theme=Setting.get().theme,
    )


@library_bp.route("/search")
def search_page():
    """Page with the search box for finding and adding new books."""
    return render_template("search_results.html", current_theme=Setting.get().theme)


@library_bp.route("/theme")
def theme_picker():
    """Theme picker page — deliberately does not inherit the active theme."""
    return render_template("theme_picker.html", current_theme=None)


@library_bp.route("/theme/set", methods=["POST"])
def set_theme():
    """Persist the chosen theme and return to the bookshelf."""
    theme = request.form.get("theme")

    if theme not in VALID_THEMES:
        return redirect(url_for("library.theme_picker"))

    setting = Setting.get()
    setting.theme = theme
    db.session.commit()

    return redirect(url_for("library.bookshelf"))