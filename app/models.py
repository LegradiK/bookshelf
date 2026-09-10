from datetime import date
from app.extensions import db
from werkzeug.security import generate_password_hash, check_password_hash


class Book(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)  # NEW
    title = db.Column(db.String(300), nullable=False)
    author = db.Column(db.String(300))
    isbn = db.Column(db.String(20), index=True)
    cover_url = db.Column(db.String(500))
    categories = db.Column(db.String(255))
    google_books_id = db.Column(db.String(100))  # unique=True REMOVED — see note below
    status = db.Column(db.String(20), default="want_to_read")
    # status: "want_to_read", "reading", "finished"
    added_on = db.Column(db.Date, default=date.today)

    logs = db.relationship(
        "ReadingLog", backref="book", lazy=True, cascade="all, delete-orphan",
        order_by="ReadingLog.date_read.desc()"
    )

    __table_args__ = (
        db.UniqueConstraint("user_id", "google_books_id", name="uq_user_google_book"),
    )

    @property
    def times_read(self):
        return len(self.logs)

    @property
    def latest_log(self):
        return self.logs[0] if self.logs else None

    @property
    def average_stars(self):
        rated = [log.stars for log in self.logs if log.stars]
        if not rated:
            return None
        return round(sum(rated) / len(rated), 1)


class ReadingLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    book_id = db.Column(db.Integer, db.ForeignKey("book.id"), nullable=False)
    date_read = db.Column(db.Date, default=date.today)
    stars = db.Column(db.Integer)  # 1-5, optional
    review = db.Column(db.Text)    # optional


class Setting(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    colour_hex = db.Column(db.String(7), nullable=True)  # e.g. "#C4B2A2"

    @classmethod
    def get(cls):
        setting = cls.query.first()
        if setting is None:
            setting = cls()
            db.session.add(setting)
            db.session.commit()
        return setting


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)

    books = db.relationship("Book", backref="owner", lazy=True, cascade="all, delete-orphan")  # NEW

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)