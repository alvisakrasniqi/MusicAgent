import hashlib
import hmac
import secrets


PBKDF2_ALGORITHM = "sha256"
PBKDF2_ITERATIONS = 390000
PBKDF2_SALT_BYTES = 16
PBKDF2_PREFIX = f"pbkdf2_{PBKDF2_ALGORITHM}"


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(PBKDF2_SALT_BYTES)
    derived_key = hashlib.pbkdf2_hmac(
        PBKDF2_ALGORITHM,
        password.encode("utf-8"),
        salt,
        PBKDF2_ITERATIONS,
    )
    return f"{PBKDF2_PREFIX}${PBKDF2_ITERATIONS}${salt.hex()}${derived_key.hex()}"


def verify_password(password: str, stored_hash: str | None) -> bool:
    if not stored_hash:
        return False

    parts = stored_hash.split("$")
    if len(parts) == 4 and parts[0].startswith("pbkdf2_"):
        _, iteration_value, salt_hex, expected_hash = parts

        try:
            iterations = int(iteration_value)
            salt = bytes.fromhex(salt_hex)
        except ValueError:
            return False

        derived_key = hashlib.pbkdf2_hmac(
            PBKDF2_ALGORITHM,
            password.encode("utf-8"),
            salt,
            iterations,
        )
        return hmac.compare_digest(derived_key.hex(), expected_hash)

    legacy_sha256 = hashlib.sha256(password.encode("utf-8")).hexdigest()
    return hmac.compare_digest(legacy_sha256, stored_hash)
