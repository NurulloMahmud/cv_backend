"""
Mongoengine documents for the accounts app.
Replaces the Django ORM models.py.
"""

import bcrypt
import mongoengine as me
from datetime import datetime


class User(me.Document):
    email = me.EmailField(required=True, unique=True)
    password_hash = me.StringField(required=True)
    first_name = me.StringField(max_length=100, default='')
    last_name = me.StringField(max_length=100, default='')
    phone_number = me.StringField(max_length=20, default='')
    bio = me.StringField(default='')
    is_active = me.BooleanField(default=True)
    date_joined = me.DateTimeField(default=datetime.utcnow)
    last_login = me.DateTimeField()

    meta = {
        'collection': 'users',
        'indexes': ['email'],
    }

    def set_password(self, raw_password: str) -> None:
        """Hash and store a plaintext password using bcrypt."""
        self.password_hash = bcrypt.hashpw(
            raw_password.encode(), bcrypt.gensalt()
        ).decode()

    def check_password(self, raw_password: str) -> bool:
        """Verify a plaintext password against the stored hash."""
        return bcrypt.checkpw(
            raw_password.encode(), self.password_hash.encode()
        )

    @property
    def id_str(self) -> str:
        return str(self.id)

    # DRF IsAuthenticated checks .is_authenticated
    @property
    def is_authenticated(self) -> bool:
        return True

    def __str__(self) -> str:
        return self.email


class BlacklistedToken(me.Document):
    token = me.StringField(required=True, unique=True)
    blacklisted_at = me.DateTimeField(default=datetime.utcnow)
    expires_at = me.DateTimeField(required=True)

    meta = {
        'collection': 'blacklisted_tokens',
        'indexes': [
            'token',
            # TTL index: MongoDB automatically removes expired documents
            {'fields': ['expires_at'], 'expireAfterSeconds': 0},
        ],
    }

    def __str__(self) -> str:
        return f'BlacklistedToken({self.token[:20]}...)'
