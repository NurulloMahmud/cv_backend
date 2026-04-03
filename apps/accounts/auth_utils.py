"""
JWT helpers and custom DRF authentication class for MongoDB-backed users.
Uses PyJWT instead of djangorestframework-simplejwt.
"""

from datetime import datetime, timedelta, timezone

import jwt
from django.conf import settings
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed

from .documents import BlacklistedToken, User


# ---------------------------------------------------------------------------
# Token generation
# ---------------------------------------------------------------------------

def generate_tokens(user) -> dict:
    """Generate access and refresh JWT tokens for a user."""
    now = datetime.now(timezone.utc)

    access_payload = {
        'user_id': str(user.id),
        'email': user.email,
        'type': 'access',
        'iat': now,
        'exp': now + timedelta(minutes=settings.JWT_ACCESS_TOKEN_LIFETIME_MINUTES),
    }
    refresh_payload = {
        'user_id': str(user.id),
        'type': 'refresh',
        'iat': now,
        'exp': now + timedelta(days=settings.JWT_REFRESH_TOKEN_LIFETIME_DAYS),
    }

    access_token = jwt.encode(
        access_payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM
    )
    refresh_token = jwt.encode(
        refresh_payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM
    )

    return {'access': access_token, 'refresh': refresh_token}


# ---------------------------------------------------------------------------
# Token decoding / validation
# ---------------------------------------------------------------------------

def decode_token(token: str, token_type: str = 'access') -> dict:
    """Decode and validate a JWT. Raises AuthenticationFailed on any error."""
    try:
        payload = jwt.decode(
            token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
        )
        if payload.get('type') != token_type:
            raise AuthenticationFailed('Invalid token type.')
        return payload
    except jwt.ExpiredSignatureError:
        raise AuthenticationFailed('Token has expired.')
    except jwt.InvalidTokenError:
        raise AuthenticationFailed('Invalid token.')


# ---------------------------------------------------------------------------
# Refresh / logout helpers
# ---------------------------------------------------------------------------

def refresh_access_token(refresh_token_str: str) -> dict:
    """
    Validate a refresh token, blacklist it (rotation), then return a new
    token pair.
    """
    if BlacklistedToken.objects(token=refresh_token_str).first():
        raise AuthenticationFailed('Token has been revoked.')

    payload = decode_token(refresh_token_str, token_type='refresh')

    user = User.objects(id=payload['user_id']).first()
    if not user or not user.is_active:
        raise AuthenticationFailed('User not found or inactive.')

    # Blacklist the used refresh token (one-time use)
    expires_at = datetime.fromtimestamp(payload['exp'], tz=timezone.utc)
    BlacklistedToken(token=refresh_token_str, expires_at=expires_at).save()

    return generate_tokens(user)


def blacklist_token(token_str: str) -> None:
    """Blacklist a refresh token on logout."""
    try:
        payload = decode_token(token_str, token_type='refresh')
        expires_at = datetime.fromtimestamp(payload['exp'], tz=timezone.utc)
        if not BlacklistedToken.objects(token=token_str).first():
            BlacklistedToken(token=token_str, expires_at=expires_at).save()
    except AuthenticationFailed:
        pass  # Already invalid — nothing to blacklist


# ---------------------------------------------------------------------------
# Custom DRF authentication class
# ---------------------------------------------------------------------------

class MongoJWTAuthentication(BaseAuthentication):
    """
    Custom DRF authentication backend that validates Bearer tokens against
    MongoDB-stored users and a blacklist collection.
    """

    def authenticate(self, request):
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        if not auth_header.startswith('Bearer '):
            return None  # No credentials supplied — let other backends try

        token = auth_header.split(' ', 1)[1].strip()

        if BlacklistedToken.objects(token=token).first():
            raise AuthenticationFailed('Token has been revoked.')

        payload = decode_token(token, token_type='access')

        user = User.objects(id=payload['user_id']).first()
        if not user or not user.is_active:
            raise AuthenticationFailed('User not found or inactive.')

        return (user, token)

    def authenticate_header(self, request) -> str:
        return 'Bearer'
