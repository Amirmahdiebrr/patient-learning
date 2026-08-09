"""
app/core/encryption.py

Transparent field-level encryption for sensitive columns, backed by
Fernet (AES-128-CBC + HMAC). Applied via SQLAlchemy TypeDecorator so
model code just declares EncryptedString() as the column type -
encryption/decryption happens automatically on every read/write, with
zero encryption logic scattered in services or routes.
"""

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import String, TypeDecorator

from app.core.config import settings

_fernet = Fernet(settings.ENCRYPTION_KEY.encode())


class EncryptedString(TypeDecorator):
    impl = String
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return _fernet.encrypt(value.encode()).decode()

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        try:
            return _fernet.decrypt(value.encode()).decode()
        except InvalidToken:
            return value