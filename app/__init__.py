"""PS2 Hub — Flask application factory."""
import os

from flask import Flask, render_template


def create_app(config_override=None):
    """Create and configure the Flask application.

    Args:
        config_override: Optional dict of config values to override defaults.

    Returns:
        Configured Flask app instance.
    """
    app = Flask(__name__)

    # Load configuration
    from app.config import Config
    app.config.from_object(Config)

    if config_override:
        app.config.update(config_override)

    # Ensure OPL directories exist
    for key in ('DVD_DIR', 'CD_DIR', 'ART_DIR', 'CFG_DIR', 'VMC_DIR', 'DOWNLOADS_DIR'):
        os.makedirs(app.config[key], exist_ok=True)

    # ── Register API blueprints ─────────────────────────────────────
    from app.routes.library import library_bp
    from app.routes.downloads import downloads_bp
    from app.routes.uploads import uploads_bp
    from app.routes.system import system_bp
    from app.routes.tasks import tasks_bp
    
    app.register_blueprint(library_bp, url_prefix='/api')
    app.register_blueprint(downloads_bp, url_prefix='/api')
    app.register_blueprint(uploads_bp, url_prefix='/api')
    app.register_blueprint(system_bp, url_prefix='/api/system')
    app.register_blueprint(tasks_bp, url_prefix='/api')

    # ── SPA entry point ─────────────────────────────────────────────
    @app.route('/')
    def index():
        return render_template('index.html')

    return app
