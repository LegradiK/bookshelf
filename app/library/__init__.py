from flask import Blueprint

library_bp = Blueprint(
    "library",
    __name__,
    template_folder="../templates",
    static_folder="../static",
)

from . import routes  # noqa: E402,F401  (import at bottom to avoid circular imports)