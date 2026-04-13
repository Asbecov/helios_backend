import base64
import binascii
import hashlib
import hmac
import os

_SCRYPT_PREFIX = "scrypt"
_SCRYPT_N = 2**14
_SCRYPT_R = 8
_SCRYPT_P = 1
_SCRYPT_DKLEN = 64
_SALT_SIZE = 16


def is_password_hash(value: str) -> bool:
    """Return True when value looks like a password hash payload."""
    return value.startswith(f"{_SCRYPT_PREFIX}$")


def hash_password(password: str) -> str:
    """Hash plaintext password using scrypt."""
    salt = os.urandom(_SALT_SIZE)
    digest = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=_SCRYPT_N,
        r=_SCRYPT_R,
        p=_SCRYPT_P,
        dklen=_SCRYPT_DKLEN,
    )
    salt_encoded = base64.urlsafe_b64encode(salt).decode("ascii")
    digest_encoded = base64.urlsafe_b64encode(digest).decode("ascii")
    return (
        f"{_SCRYPT_PREFIX}${_SCRYPT_N}${_SCRYPT_R}${_SCRYPT_P}"
        f"${salt_encoded}${digest_encoded}"
    )


def verify_password(password: str, stored_hash: str) -> bool:
    """Verify plaintext password against stored scrypt hash."""
    try:
        scheme, n_raw, r_raw, p_raw, salt_raw, expected_raw = stored_hash.split("$", 5)
        if scheme != _SCRYPT_PREFIX:
            return False

        n = int(n_raw)
        r = int(r_raw)
        p = int(p_raw)
        if n <= 1 or r <= 0 or p <= 0:
            return False

        salt = base64.urlsafe_b64decode(salt_raw.encode("ascii"))
        expected_digest = base64.urlsafe_b64decode(expected_raw.encode("ascii"))
    except (ValueError, binascii.Error):
        return False

    actual_digest = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=n,
        r=r,
        p=p,
        dklen=len(expected_digest),
    )
    return hmac.compare_digest(actual_digest, expected_digest)
