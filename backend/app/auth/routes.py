import time
import secrets as _secrets

from flask import Blueprint, redirect, request, session, current_app, jsonify
from authlib.integrations.flask_client import OAuth
from flask_jwt_extended import create_access_token
from ..extensions import db
from ..models import User, Invite

bp = Blueprint('auth', __name__)
oauth = OAuth()

GOOGLE_CONF = {
    'server_metadata_url': 'https://accounts.google.com/.well-known/openid-configuration',
    'client_kwargs': {'scope': 'openid email profile'},
}
GITHUB_CONF = {
    'api_base_url': 'https://api.github.com/',
    'access_token_url': 'https://github.com/login/oauth/access_token',
    'authorize_url': 'https://github.com/login/oauth/authorize',
    'client_kwargs': {'scope': 'user:email'},
}


def init_oauth(app):
    oauth.init_app(app)
    oauth.register('google', client_id=app.config['GOOGLE_CLIENT_ID'],
                   client_secret=app.config['GOOGLE_CLIENT_SECRET'], **GOOGLE_CONF)
    oauth.register('github', client_id=app.config['GITHUB_CLIENT_ID'],
                   client_secret=app.config['GITHUB_CLIENT_SECRET'], **GITHUB_CONF)


def _base_url() -> str:
    configured = current_app.config.get('BACKEND_URL', '')
    return configured if configured else request.host_url.rstrip('/')


# ── Server-side OAuth state store (survives proxy/cookie issues) ───────────────
# Authlib normally stores OAuth state in the Flask session cookie, which can be
# lost when running behind a tunnel (cloudflared, ngrok, etc.).  We generate the
# state ourselves, keep all flow data in this dict, and re-populate the session
# in each callback so Authlib's internal state check still passes.

_pending: dict[str, dict] = {}
_STATE_TTL = 600  # seconds


def _save(state: str, data: dict) -> None:
    now = time.time()
    _pending[state] = {**data, '_ts': now}
    stale = [k for k, v in _pending.items() if now - v['_ts'] > _STATE_TTL]
    for k in stale:
        del _pending[k]


def _pop(state: str) -> dict | None:
    entry = _pending.pop(state, None)
    if entry and time.time() - entry['_ts'] <= _STATE_TTL:
        return {k: v for k, v in entry.items() if k != '_ts'}
    return None


def _restore_session(provider: str, state: str, redirect_uri: str = '') -> None:
    """Put Authlib's expected session key back if the cookie was lost."""
    key = f'_state_{provider}_{state}'
    if key not in session:
        session[key] = {'data': {'redirect_uri': redirect_uri}, 'exp': time.time() + 3600}


# ── Invite validation ──────────────────────────────────────────────────────────

def _validate_invite(code: str) -> Invite | None:
    if not code:
        return None
    return Invite.query.filter_by(code=code, used=False).first()


# ── OAuth flow helpers ─────────────────────────────────────────────────────────

def _get_or_create_user(provider: str, sub: str, email: str, display_name: str, avatar_url: str) -> User:
    user = User.query.filter_by(oauth_provider=provider, oauth_sub=sub).first()
    if not user:
        user = User(
            email=email,
            display_name=display_name,
            avatar_url=avatar_url,
            oauth_provider=provider,
            oauth_sub=sub,
        )
        db.session.add(user)
    else:
        user.display_name = display_name
        user.avatar_url = avatar_url
    return user


def _consume_invite(invite: Invite, user: User):
    invite.used = True
    invite.used_by_id = user.id
    db.session.commit()


def _redirect_with_token(user: User, native: bool = False) -> str:
    token = create_access_token(identity=str(user.id))
    if native:
        scheme = current_app.config.get('NATIVE_CALLBACK_SCHEME', 'mangaupdates')
        return f'{scheme}://auth/callback?token={token}'
    frontend = current_app.config['FRONTEND_URL']
    return f'{frontend}/auth/callback#{token}'


# ── Google signup ──────────────────────────────────────────────────────────────

@bp.route('/google')
def google_login():
    invite_code = request.args.get('invite', '')
    invite = _validate_invite(invite_code)
    if not invite:
        return jsonify({'error': 'Valid invite code required'}), 403
    state = _secrets.token_urlsafe(24)
    redirect_uri = _base_url() + '/auth/google/callback'
    _save(state, {'invite_code': invite_code, 'native': request.args.get('native') == '1', 'redirect_uri': redirect_uri})
    return oauth.google.authorize_redirect(redirect_uri, state=state)


@bp.route('/google/callback')
def google_callback():
    state = request.args.get('state', '')
    data = _pop(state)
    if data is None:
        return jsonify({'error': 'Invalid or expired OAuth state'}), 400
    _restore_session('google', state, data.get('redirect_uri', ''))

    token = oauth.google.authorize_access_token()
    userinfo = token.get('userinfo') or oauth.google.userinfo()
    invite = _validate_invite(data.get('invite_code'))
    if not invite:
        return jsonify({'error': 'Invite expired or invalid'}), 403

    user = _get_or_create_user(
        provider='google',
        sub=userinfo['sub'],
        email=userinfo['email'],
        display_name=userinfo.get('name', userinfo['email']),
        avatar_url=userinfo.get('picture'),
    )
    _consume_invite(invite, user)
    return redirect(_redirect_with_token(user, native=data.get('native', False)))


# ── GitHub signup ──────────────────────────────────────────────────────────────

@bp.route('/github')
def github_login():
    invite_code = request.args.get('invite', '')
    invite = _validate_invite(invite_code)
    if not invite:
        return jsonify({'error': 'Valid invite code required'}), 403
    state = _secrets.token_urlsafe(24)
    redirect_uri = _base_url() + '/auth/github/callback'
    _save(state, {'invite_code': invite_code, 'native': request.args.get('native') == '1', 'redirect_uri': redirect_uri})
    return oauth.github.authorize_redirect(redirect_uri, state=state)


@bp.route('/github/callback')
def github_callback():
    state = request.args.get('state', '')
    data = _pop(state)
    if data is None:
        return jsonify({'error': 'Invalid or expired OAuth state'}), 400
    _restore_session('github', state, data.get('redirect_uri', ''))

    token = oauth.github.authorize_access_token()
    resp = oauth.github.get('user', token=token)
    profile = resp.json()
    email_resp = oauth.github.get('user/emails', token=token)
    emails = email_resp.json()
    primary_email = next((e['email'] for e in emails if e.get('primary')), profile.get('email', ''))

    invite = _validate_invite(data.get('invite_code'))
    if not invite:
        return jsonify({'error': 'Invite expired or invalid'}), 403

    user = _get_or_create_user(
        provider='github',
        sub=str(profile['id']),
        email=primary_email,
        display_name=profile.get('name') or profile.get('login', ''),
        avatar_url=profile.get('avatar_url'),
    )
    _consume_invite(invite, user)
    return redirect(_redirect_with_token(user, native=data.get('native', False)))


# ── Returning user login ───────────────────────────────────────────────────────

@bp.route('/google/login')
def google_login_returning():
    state = _secrets.token_urlsafe(24)
    redirect_uri = _base_url() + '/auth/google/login/callback'
    _save(state, {'native': request.args.get('native') == '1', 'redirect_uri': redirect_uri})
    return oauth.google.authorize_redirect(redirect_uri, state=state)


@bp.route('/google/login/callback')
def google_login_returning_callback():
    state = request.args.get('state', '')
    data = _pop(state)
    if data is None:
        return jsonify({'error': 'Invalid or expired OAuth state'}), 400
    _restore_session('google', state, data.get('redirect_uri', ''))

    token = oauth.google.authorize_access_token()
    userinfo = token.get('userinfo') or oauth.google.userinfo()
    user = User.query.filter_by(oauth_provider='google', oauth_sub=userinfo['sub']).first()
    if not user:
        frontend = current_app.config['FRONTEND_URL']
        return redirect(f'{frontend}/login?error=no_account')
    user.display_name = userinfo.get('name', user.display_name)
    user.avatar_url = userinfo.get('picture', user.avatar_url)
    db.session.commit()
    return redirect(_redirect_with_token(user, native=data.get('native', False)))


@bp.route('/github/login')
def github_login_returning():
    state = _secrets.token_urlsafe(24)
    redirect_uri = _base_url() + '/auth/github/login/callback'
    _save(state, {'native': request.args.get('native') == '1', 'redirect_uri': redirect_uri})
    return oauth.github.authorize_redirect(redirect_uri, state=state)


@bp.route('/github/login/callback')
def github_login_returning_callback():
    state = request.args.get('state', '')
    data = _pop(state)
    if data is None:
        return jsonify({'error': 'Invalid or expired OAuth state'}), 400
    _restore_session('github', state, data.get('redirect_uri', ''))

    token = oauth.github.authorize_access_token()
    resp = oauth.github.get('user', token=token)
    profile = resp.json()
    user = User.query.filter_by(oauth_provider='github', oauth_sub=str(profile['id'])).first()
    if not user:
        frontend = current_app.config['FRONTEND_URL']
        return redirect(f'{frontend}/login?error=no_account')
    user.display_name = profile.get('name') or profile.get('login', user.display_name)
    user.avatar_url = profile.get('avatar_url', user.avatar_url)
    db.session.commit()
    return redirect(_redirect_with_token(user, native=data.get('native', False)))


# ── Me ─────────────────────────────────────────────────────────────────────────

@bp.route('/me')
def me():
    from flask_jwt_extended import verify_jwt_in_request, get_jwt_identity
    try:
        verify_jwt_in_request()
        user_id = get_jwt_identity()
        user = User.query.get(int(user_id))
        if not user:
            return jsonify({'error': 'Not found'}), 404
        return jsonify(user.to_dict())
    except Exception:
        return jsonify({'error': 'Unauthorised'}), 401
