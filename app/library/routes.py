from flask import render_template, request, redirect, url_for, abort, session

from . import library_bp
from app.models import db, Book, Setting, User
from app.colours import COLOUR_GROUPS, COLOURS_BY_ID, VALID_HEXES, DEFAULT_HEX
from app.colour_shades import site_palette
from app.auth.routes import login_required

import io
from datetime import date
from flask import send_file
from reportlab.lib.pagesizes import landscape, letter
from reportlab.lib.colors import HexColor
from reportlab.pdfgen import canvas
from reportlab.pdfbase.pdfmetrics import stringWidth
import unicodedata


def _current_colour_hex() -> str:
    setting = Setting.get()
    if setting.colour_hex and setting.colour_hex in VALID_HEXES:
        return setting.colour_hex
    return DEFAULT_HEX

def normalize_text(s: str) -> str:
    if not s:
        return ""
    return "".join(
        c for c in unicodedata.normalize("NFD", s)
        if unicodedata.category(c) != "Mn"  # strip combining accent marks
    ).lower()

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

@library_bp.route("/about")
def about():
    "this page explains what this web app is for"
    return render_template("about.html")

@library_bp.route("/bookshelf")
@login_required
def bookshelf():
    user = User.query.get(session["user_id"])

    sort = request.args.get("sort", "recent")
    selected_genre = request.args.get("genre", "")
    selected_author = request.args.get("author", "")
    active_status = request.args.get("status", "all")
    page = request.args.get('page', 1, type=int)
    query_text = request.args.get("q", "").strip()

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

    # Build the SQL-level query with the filters that DON'T need accent-insensitivity
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

    # Fetch everything matching the SQL filters, then apply text search in Python
    all_matching = query.all()

    if query_text:
        norm_q = normalize_text(query_text)
        all_matching = [
            b for b in all_matching
            if norm_q in normalize_text(b.title) or norm_q in normalize_text(b.author)
        ]

    if sort == "stars":
        all_matching.sort(key=lambda b: b.average_stars or 0, reverse=True)

    # Now that filtering/sorting are locked in, paginate in Python
    total_count = len(all_matching)
    limit = page * PER_PAGE
    books = all_matching[:limit]
    has_more = total_count > limit

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
        query=query_text,
        page=page,
        has_more=has_more,
        user_name=user.username if user else None
    )

import requests

OL = "https://openlibrary.org"

# Generic labels that don't help as genres
SKIP_SUBJECTS = {"readers", "media tie-in"}


def get_ol_subjects(isbn):
    """Edition subjects, falling back to the work's subjects via the 'works' key."""
    try:
        resp = requests.get(f"{OL}/isbn/{isbn}.json", timeout=5)
        if not resp.ok:
            return []
        edition = resp.json()
    except (requests.RequestException, ValueError):
        return []

    subjects = edition.get("subjects", [])
    if subjects:
        return subjects

    works = edition.get("works", [])
    work_key = works[0].get("key") if works else None  # e.g. "/works/OL20848685W"
    if not work_key:
        return []

    try:
        resp = requests.get(f"{OL}{work_key}.json", timeout=5)
        if resp.ok:
            return resp.json().get("subjects", [])
    except (requests.RequestException, ValueError):
        pass
    return []


def _ol_subjects_by_title(title, author):
    params = {"title": title, "fields": "subject", "limit": 1}
    if author:
        params["author"] = author
    try:
        resp = requests.get(f"{OL}/search.json", params=params, timeout=5)
        if resp.ok:
            docs = resp.json().get("docs", [])
            return docs[0].get("subject", []) if docs else []
    except (requests.RequestException, ValueError):
        pass
    return []


def _clean_subjects(subjects, cap=8):
    cleaned, seen = [], set()
    for s in subjects:
        s = s.strip()
        if not s or ":" in s:  # drops "collectionID:swOTyr" etc.
            continue
        if " / " in s:  # "JUVENILE FICTION / Action & Adventure" -> "Action & Adventure"
            s = s.split(" / ")[-1]
        s = s.removesuffix(", fiction").strip()
        if s.isupper():
            s = s.title()
        key = s.lower()
        if key in SKIP_SUBJECTS or key in seen or len(s) >= 40:
            continue
        seen.add(key)
        cleaned.append(s)
        if len(cleaned) >= cap:
            break
    return cleaned


@library_bp.route("/fetch-genres")
@login_required
def fetch_genres():
    """Look up subjects/genres from Open Library, triggered manually by the user."""
    isbn = request.args.get("isbn", "").strip().replace("-", "")
    title = request.args.get("title", "").strip()
    author = request.args.get("author", "").strip()

    subjects = []
    if isbn:
        subjects = get_ol_subjects(isbn)
    if not subjects and title:
        subjects = _ol_subjects_by_title(title, author)

    cleaned = _clean_subjects(subjects)
    if not cleaned:
        return {"genres": [], "message": "No genres found on Open Library."}
    return {"genres": cleaned}

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

def _draw_star(c, cx, cy, size, fill_color):
    """Draw a simple 5-point star centered at (cx, cy)."""
    import math
    points = []
    for i in range(10):
        angle = math.pi / 2 + i * math.pi / 5
        r = size if i % 2 == 0 else size * 0.4
        points.append((cx + r * math.cos(angle), cy + r * math.sin(angle)))

    c.setFillColor(fill_color)
    c.setStrokeColor(fill_color)
    path = c.beginPath()
    path.moveTo(*points[0])
    for x, y in points[1:]:
        path.lineTo(x, y)
    path.close()
    c.drawPath(path, fill=1, stroke=0)

def _draw_trophy(c, cx, cy, size, fill_color, outline_color=None):
    """Draw a simple trophy centered at (cx, cy). `size` controls overall scale."""
    from reportlab.lib.colors import HexColor

    outline_color = outline_color or fill_color
    c.setFillColor(fill_color)
    c.setStrokeColor(outline_color)

    cup_w = size * 1.1
    cup_h = size * 1.0
    stem_w = size * 0.22
    stem_h = size * 0.35
    base_w = size * 1.0
    base_h = size * 0.18

    # Cup body (rounded rect)
    c.roundRect(cx - cup_w / 2, cy, cup_w, cup_h, size * 0.25, fill=1, stroke=0)

    # Handles (two arcs, drawn as open bezier-ish curves via ellipse halves)
    handle_r = size * 0.32
    c.setLineWidth(size * 0.12)
    c.setStrokeColor(fill_color)
    c.ellipse(cx - cup_w / 2 - handle_r, cy + cup_h * 0.15,
              cx - cup_w / 2 + handle_r * 0.3, cy + cup_h * 0.75,
              fill=0, stroke=1)
    c.ellipse(cx + cup_w / 2 - handle_r * 0.3, cy + cup_h * 0.15,
              cx + cup_w / 2 + handle_r, cy + cup_h * 0.75,
              fill=0, stroke=1)

    # Stem
    c.setFillColor(fill_color)
    c.rect(cx - stem_w / 2, cy - stem_h, stem_w, stem_h, fill=1, stroke=0)

    # Base
    c.roundRect(cx - base_w / 2, cy - stem_h - base_h, base_w, base_h, size * 0.06, fill=1, stroke=0)


@library_bp.route("/achievements/certificate")
@login_required
def achievement_certificate():
    user = User.query.get(session["user_id"])

    finished_count = Book.query.filter(
        Book.user_id == session["user_id"],
        Book.status == "finished"
    ).count()

    achieved = [m for m in MILESTONES if finished_count >= m]
    if not achieved:
        abort(404)  # nothing earned yet — no certificate to generate

    milestone = achieved[-1]  # most recent (highest) milestone reached

    buffer = io.BytesIO()
    page_size = landscape(letter)
    c = canvas.Canvas(buffer, pagesize=page_size)
    width, height = page_size

    # Palette — bright and friendly
    gold = HexColor("#F5A623")
    teal = HexColor("#2FB6A9")
    coral = HexColor("#FF6F61")
    purple = HexColor("#8E6FD8")
    navy = HexColor("#2E3A59")
    star_colors = [gold, teal, coral, purple]

    # Background
    c.setFillColor(HexColor("#FFFBF2"))
    c.rect(0, 0, width, height, fill=1, stroke=0)

    # Decorative border (double rounded rect)
    margin = 24
    c.setStrokeColor(teal)
    c.setLineWidth(6)
    c.roundRect(margin, margin, width - 2 * margin, height - 2 * margin, 24, fill=0, stroke=1)
    c.setStrokeColor(gold)
    c.setLineWidth(2)
    c.roundRect(margin + 10, margin + 10, width - 2 * (margin + 10), height - 2 * (margin + 10), 18, fill=0, stroke=1)

    # Scattered stars along the top and bottom
    star_positions = [
        # 2 stars on the left side (vertically stacked, mid-height)
        (60, height / 2 - 70),
        (60, height / 2 + 70),

        # 2 stars on the right side (mirrored)
        (width - 60, height / 2 - 70),
        (width - 60, height / 2 + 70),

        # 4 stars along the bottom
        (85, height - 95),
        (width / 2 - 160, height - 55),
        (width / 2 + 160, height - 55),
        (width - 85, height - 95),

        # 4 stars along the top (mirrored y of bottom row)
        (85, 95),
        (width / 2 - 160, 55),
        (width / 2 + 160, 55),
        (width - 85, 95),
    ]
    for i, (sx, sy) in enumerate(star_positions):
        _draw_star(c, sx, sy, 14, star_colors[i % len(star_colors)])

    # Title
    c.setFillColor(navy)
    c.setFont("Helvetica-Bold", 42)
    title = "Certificate of Achievement"
    c.drawCentredString(width / 2, height - 150, title)

    # Trophy above the title
    _draw_trophy(c, width / 2, height - 200, 22, gold)

    # Subtitle
    c.setFont("Helvetica", 22)
    c.setFillColor(navy)
    c.drawCentredString(width / 2, height - 250, "This is a certificate for")

    # Name
    c.setFont("Helvetica-Bold", 36)
    c.setFillColor(coral)
    name = user.username if user else "Reader"
    c.drawCentredString(width / 2, height - 310, name)
    c.setLineWidth(1)
    c.setStrokeColor(navy)
    line_w = stringWidth(name, "Helvetica", 12) + 40
    c.line(width / 2 - line_w / 2, 80, width / 2 + line_w / 2, 80)

    # Achievement line
    c.setFont("Helvetica", 20)
    c.setFillColor(navy)
    achievement_text = f"For a wonderful love of reading and the curiosity to explore {milestone} book{'s' if milestone != 1 else ''}!"
    c.drawCentredString(width / 2, height - 355, achievement_text)

    # Encouraging line
    c.setFont("Helvetica-BoldOblique", 14)
    c.setFillColor(teal)

    lines = [
    "You've shown real dedication and a love of stories.",
    "Every book you read makes your imagination even bigger.",
    "We're so proud of you!",
    ]

    line_height = 22  # spacing between lines, in points — adjust to taste
    start_y = height - 410

    for i, line in enumerate(lines):
        c.drawCentredString(width / 2, start_y - (i * line_height), line)
    
    # Date, bottom center
    c.setFont("Helvetica", 12)
    c.setFillColor(navy)
    today_str = date.today().strftime("%d %B %Y")
    c.drawCentredString(width / 2, 90, today_str)
    c.setLineWidth(1)
    c.setStrokeColor(navy)
    line_w = stringWidth(today_str, "Helvetica", 12) + 40
    c.line(width / 2 - line_w / 2, 80, width / 2 + line_w / 2, 80)

    c.showPage()
    c.save()
    buffer.seek(0)

    filename = f"{name.replace(' ', '_')}_certificate_{milestone}_books.pdf"
    return send_file(
        buffer,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=filename,
    )