from flask import Blueprint, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from ..models import User

bp = Blueprint('user', __name__)


@bp.get('/me')
@jwt_required()
def me():
    user = User.query.get(int(get_jwt_identity()))
    if not user:
        return jsonify({'error': 'Not found'}), 404
    return jsonify(user.to_dict())
