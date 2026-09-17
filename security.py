import hashlib
import secrets


def hash_password(password: str, salt: str = None):
    if salt is None:
        salt = secrets.token_hex(16)
    computed = hashlib.sha256((password + salt).encode()).hexdigest()
    return computed, salt
