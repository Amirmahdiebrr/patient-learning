"""
scripts/generate_all_secrets.py

Generates every secret this project needs, in one shot, and prints
them ready to paste into .env:
    - ACCESS_COOKIE_SECRET  (signs the QR access/profile cookies)
    - JWT_SECRET_KEY        (signs admin JWTs)
    - ENCRYPTION_KEY        (Fernet key, encrypts patient PII at rest)
    - SEARCH_HASH_KEY       (HMAC key for blind-index lookups - MUST
                              differ from ENCRYPTION_KEY)
    - BOOTSTRAP_SUPER_ADMIN_PASSWORD (one-time super_admin password)

Replaces the old separate scripts/generate_encryption_key.py and
scripts/generate_search_hash_key.py - use this one instead.

Run with:
    python -m scripts.generate_all_secrets

IMPORTANT:
    - Never commit real secrets to git (.env is already gitignored).
    - If you rotate ENCRYPTION_KEY after real patient data exists,
      every encrypted column (national_id, phone_number,
      insurance_code) becomes undecryptable - only rotate it before
      any real data is written, or run a proper re-encryption
      migration.
    - After bootstrapping the first super_admin, clear
      BOOTSTRAP_SUPER_ADMIN_EMAIL / BOOTSTRAP_SUPER_ADMIN_PASSWORD
      from .env so the seed script won't try to recreate it.
"""

import secrets
import string

from cryptography.fernet import Fernet


def generate_strong_password(length: int = 20) -> str:
    alphabet = string.ascii_letters + string.digits + "!@#%^&*_-+="
    return "".join(secrets.choice(alphabet) for _ in range(length))


def main() -> None:
    access_cookie_secret = secrets.token_urlsafe(48)
    jwt_secret_key = secrets.token_urlsafe(48)
    encryption_key = Fernet.generate_key().decode()
    search_hash_key = secrets.token_hex(32)
    bootstrap_password = generate_strong_password()

    print("# Paste these into your .env file (replace the existing values):")
    print()
    print(f"ACCESS_COOKIE_SECRET={access_cookie_secret}")
    print(f"JWT_SECRET_KEY={jwt_secret_key}")
    print(f"ENCRYPTION_KEY={encryption_key}")
    print(f"SEARCH_HASH_KEY={search_hash_key}")
    print(f"BOOTSTRAP_SUPER_ADMIN_PASSWORD={bootstrap_password}")
    print()
    print("# Reminder: ENCRYPTION_KEY and SEARCH_HASH_KEY must always be")
    print("# two DIFFERENT secrets - never reuse one for the other.")


if __name__ == "__main__":
    main()