import os
from config import Config
from app.extensions import db
from flask import Flask, session
from app.models import db, User


def create_app(config_class=Config):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_class)

    os.makedirs(app.instance_path, exist_ok=True)

    db.init_app(app)

    from app.books.routes import books_bp
    from app.library.routes import library_bp
    from app.auth.routes import auth_bp
    app.register_blueprint(books_bp)
    app.register_blueprint(library_bp)
    app.register_blueprint(auth_bp)

    with app.app_context():
        db.create_all()

    @app.context_processor
    def inject_user():
        user = None
        if "user_id" in session:
            user = User.query.get(session["user_id"])
        return dict(current_user=user)

    return app