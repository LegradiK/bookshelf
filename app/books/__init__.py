from flask import Blueprint

books_bp = Blueprint(
    "books",
    __name__,
    template_folder="../templates",
    static_folder="../static",
)

from . import routes  # noqa: E402,F401  (import at bottom to avoid circular imports)