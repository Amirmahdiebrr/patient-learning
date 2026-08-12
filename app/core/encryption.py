"""
app/core/encryption.py

Transparent field-level encryption for sensitive columns, backed by
Fernet (AES-128-CBC + HMAC). Applied via SQLAlchemy TypeDecorator so
model code just declares EncryptedString() as the column type -
encryption/decryption happens automatically on every read/write, with
zero encryption logic scattered in services or routes.

hash_lookup_value() is a SEPARATE, deterministic HMAC-SHA256 digest
used only for exact-match lookups (e.g. matching a referral's national
ID against an existing patient's, without decrypting every row).
Fernet ciphertext is non-deterministic (includes a nonce), so it can
never be used for equality search - this hash column exists precisely
to enable that lookup while the actual value stays encrypted.
"""

import hashlib
import hmac

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


def hash_lookup_value(value: str | None) -> str | None:
    if value is None or not value.strip():
        return None
    secret = settings.ENCRYPTION_KEY.encode()
    return hmac.new(secret, value.strip().encode(), hashlib.sha256).hexdigest()


def decrypt_value_raw(ciphertext: str) -> str | None:
    """
    Used only by the one-off data migration that backfills
    national_id_hash for rows encrypted before this hash column
    existed. Not for use in application code - go through
    EncryptedString (i.e. read the ORM attribute) instead.
    """
    try:
        return _fernet.decrypt(ciphertext.encode()).decode()
    except InvalidToken:
        return None