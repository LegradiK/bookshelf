from datetime import date
from app.extensions import db


class Book(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(300), nullable=False)
    author = db.Column(db.String(300))
    cover_url = db.Column(db.String(500))
    google_books_id = db.Column(db.String(100), unique=True)
    status = db.Column(db.String(20), default="want_to_read")
    # status: "want_to_read", "reading", "finished"
    added_on = db.Column(db.Date, default=date.today)

    logs = db.relationship(
        "ReadingLog", backref="book", lazy=True, cascade="all, delete-orphan",
        order_by="ReadingLog.date_read.desc()"
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
    """Single-row table for simple site-wide settings like the chosen theme."""
    id = db.Column(db.Integer, primary_key=True)
    theme = db.Column(db.String(20), default=None)  # "dragons" or "unicorns"

    @staticmethod
    def get():
        setting = Setting.query.first()
        if not setting:
            setting = Setting()
            db.session.add(setting)
            db.session.commit()
        return setting
