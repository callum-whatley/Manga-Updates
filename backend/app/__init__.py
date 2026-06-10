from flask import Flask
from werkzeug.middleware.proxy_fix import ProxyFix
from .extensions import db, migrate, jwt, cors
from config import Config


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1, x_prefix=1)

    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)
    allowed = [app.config['FRONTEND_URL']] + [
        o.strip() for o in app.config['CAPACITOR_ORIGINS'].split(',') if o.strip()
    ]
    cors.init_app(app, resources={r'/api/*': {'origins': allowed}})

    from .auth.routes import bp as auth_bp, init_oauth
    from .api.manga import bp as manga_bp
    from .api.user import bp as user_bp
    from .api.scraper import bp as scraper_bp
    from .api.reader import bp as reader_bp
    from .cli import register_cli
    from .scheduler import start_scheduler

    init_oauth(app)
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(manga_bp, url_prefix='/api/manga')
    app.register_blueprint(user_bp, url_prefix='/api/user')
    app.register_blueprint(scraper_bp, url_prefix='/api/scraper')
    app.register_blueprint(reader_bp, url_prefix='/api/reader')
    register_cli(app)
    start_scheduler(app)

    return app
