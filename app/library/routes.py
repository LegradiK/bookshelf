from flask import render_template, request, redirect, url_for, abort, session

from . import library_bp
from app.models import db, Book, Setting, User, ReadingLog
from app.colours import COLOUR_GROUPS, COLOURS_BY_ID, VALID_HEXES, DEFAULT_HEX
from app.colour_shades import site_palette

from functools import wraps


def _current_colour_hex() -> str:
    setting = Setting.get()
    if setting.colour_hex and setting.colour_hex in VALID_HEXES:
        return setting.colour_hex
    return DEFAULT_HEX

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)
    return decorated


@library_bp.route("/")
def index():
    if "user_id" not in session:
        return redirect(url_for("auth.login"))
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


@library_bp.route("/add-book", methods=["POST"])
def add_book():
    user_id = session["user_id"]
    google_id = request.form["google_books_id"]

    book = Book.query.filter_by(google_books_id=google_id, user_id=user_id).first()
    if not book:
        # fetch from Google Books API and create it
        book = Book(
            user_id=user_id,
            google_books_id=google_id, 
            title=..., 
            author=..., 
            cover_url=...
            )
        db.session.add(book)
        db.session.flush()  # get book.id before commit

    log = ReadingLog(
        book=book, 
        stars=request.form.get("stars", type=int), 
        review=request.form.get("review")
        )
    db.session.add(log)

    book.status = "finished"
    db.session.commit()

    return redirect(url_for("library.bookshelf"))

@library_bp.route("/bookshelf")
@login_required
def bookshelf():
    user = User.query.get(session["user_id"])   

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

    query = Book.query.filter(Book.user_id == session["user_id"])

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
        user_name=user.username if user else None
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