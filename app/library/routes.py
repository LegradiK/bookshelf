from flask import render_template, request, redirect, url_for, abort, session

from . import library_bp
from app.models import db, Book, Setting, User
from app.colours import COLOUR_GROUPS, COLOURS_BY_ID, VALID_HEXES, DEFAULT_HEX
from app.colour_shades import site_palette
from app.auth.routes import login_required

def _current_colour_hex() -> str:
    setting = Setting.get()
    if setting.colour_hex and setting.colour_hex in VALID_HEXES:
        return setting.colour_hex
    return DEFAULT_HEX

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

PER_PAGE = 20

@library_bp.route("/bookshelf")
@login_required
def bookshelf():
    user = User.query.get(session["user_id"])

    sort = request.args.get("sort", "recent")
    selected_genre = request.args.get("genre", "")
    selected_author = request.args.get("author", "")
    active_status = request.args.get("status", "all")
    page = request.args.get('page', 1, type=int)

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
    else:  # "recent" and "stars" both need id.desc() as a base order
        query = query.order_by(Book.id.desc())

    # Now that filters/sort are locked in, count and paginate
    total_count = query.count()
    limit = page * PER_PAGE
    books = query.limit(limit).all()
    has_more = total_count > limit

    if sort == "stars":
        books.sort(key=lambda b: b.average_stars or 0, reverse=True)

    return render_template(
        "bookshelf.html",
        books=books,
        total_count=total_count,
        genres=all_genres,
        authors=all_authors,
        sort=sort,
        selected_genre=selected_genre,
        selected_author=selected_author,
        active_status=active_status,
        page=page,
        has_more=has_more,
        user_name=user.username if user else None
    )

@library_bp.route("/search")
@login_required
def search_page():
    """Page with the search box for finding and adding new books."""
    user = User.query.get(session["user_id"]) 
    return render_template(
        "search_results.html",
        user_name=user.username if user else None
        )


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

MILESTONES = [1, 5, 10, 20, 30, 50, 80, 100, 150, 200, 300, 400, 500, 750, 1000]

@library_bp.route("/achievements")
@login_required
def achievements():
    user = User.query.get(session["user_id"])

    finished_count = Book.query.filter(
        Book.user_id == session["user_id"],
        Book.status == "finished"
    ).count()

    achieved = [m for m in MILESTONES if finished_count >= m]
    next_milestone = next((m for m in MILESTONES if finished_count < m), None)
    books_to_next = next_milestone - finished_count if next_milestone else 0

    if next_milestone:
        prev_milestone = achieved[-1] if achieved else 0
        progress_pct = int(
            (finished_count - prev_milestone) / (next_milestone - prev_milestone) * 100
        )
    else:
        progress_pct = 100  # all milestones cleared

    return render_template(
        "achievements.html",
        milestones=MILESTONES,
        achieved=achieved,
        finished_count=finished_count,
        next_milestone=next_milestone,
        books_to_next=books_to_next,
        progress_pct=progress_pct,
        user_name=user.username if user else None
    )