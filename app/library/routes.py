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

@library_bp.route("/")
def index():
    return redirect(url_for("library.bookshelf"))

@library_bp.app_context_processor
def inject_palette():
    """Makes the current colour palette available to every template,
    so base.html can set it as inline CSS custom properties without
    every view function having to pass it explicitly."""
    return {
        "palette": site_palette(_current_colour_hex()),
        "colour_groups": COLOUR_GROUPS,
    }


@library_bp.route("/bookshelf")
def bookshelf():
    sort = request.args.get("sort", "recent")
    selected_genre = request.args.get("genre", "")
    selected_author = request.args.get("author", "")
    active_status = request.args.get("status", "all")

    all_genres = set()
    for (categories,) in db.session.query(Book.categories).filter(Book.categories.isnot(None)):
        for g in categories.split(","):
            g = g.strip()
            if g:
                all_genres.add(g)
    all_genres = sorted(all_genres)

    all_authors = sorted({
        a for (a,) in db.session.query(Book.author).filter(Book.author.isnot(None))
    })

    query = Book.query

    if active_status != "all":
        query = query.filter(Book.status == active_status)
    if selected_genre:
        query = query.filter(Book.categories.ilike(f"%{selected_genre}%"))
    if selected_author:
        query = query.filter(Book.author == selected_author)

    if sort == "title":
        query = query.order_by(Book.title.asc())
    elif sort == "author":
        query = query.order_by(Book.author.asc())
    elif sort == "genre":
        query = query.order_by(Book.categories.asc())
    elif sort == "stars":
        query = query.order_by(Book.id.desc())
    else:  # "recent" fallback
        query = query.order_by(Book.id.desc())

    books = query.all()

    if sort == "stars":
        books.sort(key=lambda b: b.average_stars or 0, reverse=True)


    return render_template(
        "bookshelf.html",
        books=books,
        genres=all_genres,
        authors=all_authors,
        sort=sort,
        selected_genre=selected_genre,
        selected_author=selected_author,
        active_status=active_status,
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