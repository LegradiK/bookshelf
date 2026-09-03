from flask import render_template, request, redirect, url_for, abort

from . import library_bp
from app.models import db, Book, Setting
from app.colours import COLOUR_GROUPS, COLOURS_BY_ID, VALID_HEXES, DEFAULT_HEX
from app.colour_shades import site_palette


def _current_colour_hex() -> str:
    setting = Setting.get()
    if setting.colour_hex and setting.colour_hex in VALID_HEXES:
        return setting.colour_hex
    return DEFAULT_HEX


@library_bp.app_context_processor
def inject_palette():
    """Makes the current colour palette available to every template,
    so base.html can set it as inline CSS custom properties without
    every view function having to pass it explicitly."""
    return {
        "palette": site_palette(_current_colour_hex()),
        "colour_groups": COLOUR_GROUPS,
    }


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
    )


@library_bp.route("/search")
def search_page():
    """Page with the search box for finding and adding new books."""
    return render_template("search_results.html")


@library_bp.route("/colour/set", methods=["POST"])
def set_colour():
    """Persist the chosen colour and return to wherever the picker was opened from."""
    colour_id = request.form.get("colour_id")
    swatch = COLOURS_BY_ID.get(colour_id)

    if swatch is None:
        abort(400)

    setting = Setting.get()
    setting.colour_hex = swatch["hex"]
    db.session.commit()

    next_url = request.form.get("next") or url_for("library.bookshelf")
    return redirect(next_url)