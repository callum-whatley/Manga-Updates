from flask import Flask
from .extensions import db, migrate, jwt, cors
from config import Config


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)
    cors.init_app(app, resources={r'/api/*': {'origins': app.config['FRONTEND_URL']}})

    from .auth.routes import bp as auth_bp, init_oauth
    from .api.manga import bp as manga_bp
    from .api.user import bp as user_bp
    from .cli import register_cli

    init_oauth(app)
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(manga_bp, url_prefix='/api/manga')
    app.register_blueprint(user_bp, url_prefix='/api/user')
    register_cli(app)

    return app
