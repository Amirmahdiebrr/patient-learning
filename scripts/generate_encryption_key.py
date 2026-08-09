"""
scripts/generate_encryption_key.py

Run once to generate a Fernet key for ENCRYPTION_KEY in .env:
    python -m scripts.generate_encryption_key
"""

from cryptography.fernet import Fernet

if __name__ == "__main__":
    print(Fernet.generate_key().decode())