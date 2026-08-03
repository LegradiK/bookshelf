import os
from flask import Flask
from config import Config
from app.extensions import db


def create_app(config_class=Config):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_class)

    os.makedirs(app.instance_path, exist_ok=True)

    db.init_app(app)

    from app.books.routes import books_bp
    from app.library.routes import library_bp
    app.register_blueprint(books_bp)
    app.register_blueprint(library_bp)

    with app.app_context():
        db.create_all()

    @app.context_processor
    def inject_theme():
        from app.models import Setting
        setting = Setting.get()
        return {"current_theme": setting.theme or "dragons"}

    return app
