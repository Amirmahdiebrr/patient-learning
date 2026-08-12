"""
scripts/generate_search_hash_key.py

Run once to generate a value for SEARCH_HASH_KEY in .env:
    python -m scripts.generate_search_hash_key

Must be a DIFFERENT secret than ENCRYPTION_KEY - never reuse keys
across two different cryptographic purposes.
"""

import secrets

if __name__ == "__main__":
    print(secrets.token_hex(32))