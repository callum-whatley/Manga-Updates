import os


class Config:
    SECRET_KEY = os.environ['SECRET_KEY']
    SQLALCHEMY_DATABASE_URI = os.environ['DATABASE_URL']
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JWT_SECRET_KEY = os.environ['JWT_SECRET_KEY']
    JWT_ACCESS_TOKEN_EXPIRES = 60 * 60 * 24 * 7  # 7 days

    GOOGLE_CLIENT_ID = os.environ['GOOGLE_CLIENT_ID']
    GOOGLE_CLIENT_SECRET = os.environ['GOOGLE_CLIENT_SECRET']
    GITHUB_CLIENT_ID = os.environ['GITHUB_CLIENT_ID']
    GITHUB_CLIENT_SECRET = os.environ['GITHUB_CLIENT_SECRET']

    FRONTEND_URL = os.environ.get('FRONTEND_URL', 'http://localhost:5173')
    BACKEND_URL = os.environ.get('BACKEND_URL', '').rstrip('/')

    SESSION_COOKIE_SAMESITE = 'None'
    SESSION_COOKIE_SECURE = True

    NATIVE_CALLBACK_SCHEME = os.environ.get('NATIVE_CALLBACK_SCHEME', 'mangaupdates')
    CAPACITOR_ORIGINS = os.environ.get('CAPACITOR_ORIGINS', 'capacitor://localhost,http://localhost,https://localhost')

    @property
    def ALLOWED_ORIGINS(self):
        extra = [o.strip() for o in self.CAPACITOR_ORIGINS.split(',') if o.strip()]
        return [self.FRONTEND_URL] + extra
