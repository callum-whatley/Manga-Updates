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


# ── Invite validation ──────────────────────────────────────────────────────────

def _validate_invite(code: str) -> Invite | None:
    if not code:
        return None
    invite = Invite.query.filter_by(code=code, used=False).first()
    return invite


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


def _redirect_with_token(user: User) -> str:
    token = create_access_token(identity=str(user.id))
    frontend = current_app.config['FRONTEND_URL']
    return f'{frontend}/auth/callback?token={token}'


# ── Google ─────────────────────────────────────────────────────────────────────

@bp.route('/google')
def google_login():
    invite_code = request.args.get('invite', '')
    invite = _validate_invite(invite_code)
    if not invite:
        return jsonify({'error': 'Valid invite code required'}), 403
    session['invite_code'] = invite_code
    redirect_uri = request.host_url.rstrip('/') + '/auth/google/callback'
    return oauth.google.authorize_redirect(redirect_uri)


@bp.route('/google/callback')
def google_callback():
    token = oauth.google.authorize_access_token()
    userinfo = token.get('userinfo') or oauth.google.userinfo()
    invite_code = session.pop('invite_code', None)
    invite = _validate_invite(invite_code)
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
    return redirect(_redirect_with_token(user))


# ── GitHub ─────────────────────────────────────────────────────────────────────

@bp.route('/github')
def github_login():
    invite_code = request.args.get('invite', '')
    invite = _validate_invite(invite_code)
    if not invite:
        return jsonify({'error': 'Valid invite code required'}), 403
    session['invite_code'] = invite_code
    redirect_uri = request.host_url.rstrip('/') + '/auth/github/callback'
    return oauth.github.authorize_redirect(redirect_uri)


@bp.route('/github/callback')
def github_callback():
    token = oauth.github.authorize_access_token()
    resp = oauth.github.get('user', token=token)
    profile = resp.json()
    email_resp = oauth.github.get('user/emails', token=token)
    emails = email_resp.json()
    primary_email = next((e['email'] for e in emails if e.get('primary')), profile.get('email', ''))

    invite_code = session.pop('invite_code', None)
    invite = _validate_invite(invite_code)
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
    return redirect(_redirect_with_token(user))


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
