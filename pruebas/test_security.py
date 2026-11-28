import secrets

import pytest

from api.security import hash_password, verify_password


@pytest.mark.parametrize("password", [
    "123456",
    "Password123!",
    "Madrid2026",
    "a" * 65,
])
def test_reject_weak_password(password):
    with pytest.raises(ValueError):
        hash_password(password)


def test_password_hash_and_verification():
    password = secrets.token_urlsafe(32)
    hashed = hash_password(password)

    assert hashed.startswith("$argon2id$")
    assert verify_password(password, hashed)
    assert not verify_password("Incorrecta", hashed)
    assert hashed != hash_password(password)