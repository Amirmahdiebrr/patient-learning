"""
app/core/encryption.py

Transparent field-level encryption for sensitive columns, backed by
Fernet (AES-128-CBC + HMAC). Applied via SQLAlchemy TypeDecorator so
model code just declares EncryptedString() as the column type -
encryption/decryption happens automatically on every read/write.

blind_index() is a SEPARATE, deterministic HMAC-SHA256 digest used
only for exact-match lookups (e.g. matching a referral's national ID
against an existing patient's, without decrypting every row). It is
keyed by SEARCH_HASH_KEY, a secret DIFFERENT from ENCRYPTION_KEY (see
scripts/generate_search_hash_key.py). Falls back to ENCRYPTION_KEY if
SEARCH_HASH_KEY hasn't been set yet, so the app doesn't crash on a
fresh checkout - set SEARCH_HASH_KEY in .env as soon as possible.

hash_lookup_value is kept as a backward-compatible alias of
blind_index (onboarding.py, referral_matching_service.py,
admin_referrals.py, referrals_public.py already use that name).
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


def blind_index(value: str | None) -> str | None:
    if value is None or not value.strip():
        return None
    key = (settings.SEARCH_HASH_KEY or settings.ENCRYPTION_KEY).encode()
    return hmac.new(key, value.strip().encode(), hashlib.sha256).hexdigest()


# Backward-compatible alias - keep both names importable.
hash_lookup_value = blind_index


def decrypt_value_raw(ciphertext: str) -> str | None:
    """
    Used only by one-off data migrations that need to decrypt a raw
    ciphertext value outside of the ORM. Not for use in application
    code - go through EncryptedString (i.e. read the ORM attribute)
    instead.
    """
    try:
        return _fernet.decrypt(ciphertext.encode()).decode()
    except InvalidToken:
        return None