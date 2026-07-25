from datetime import timedelta

import pytest
from cryptography.fernet import Fernet

from app.core.exceptions import SecretCryptoError
from app.core.security import (
    ProviderAPIKeyCipher,
    create_access_token,
    decode_access_token,
    get_password_hash,
    verify_password,
)


def test_password_hash_can_be_verified() -> None:
    hashed_password = get_password_hash("correct horse battery staple")

    assert hashed_password != "correct horse battery staple"
    assert verify_password("correct horse battery staple", hashed_password)
    assert not verify_password("wrong password", hashed_password)


def test_access_token_decodes_and_rejects_expired_or_corrupt_tokens() -> None:
    token = create_access_token({"sub": "user-1"}, expires_delta=timedelta(minutes=1))

    assert decode_access_token(token)["sub"] == "user-1"  # type: ignore[index]
    assert decode_access_token(
        create_access_token({"sub": "user-1"}, expires_delta=timedelta(seconds=-1))
    ) is None
    assert decode_access_token("not.a.jwt") is None


def test_provider_api_key_cipher_round_trip_and_previous_key_rotation() -> None:
    previous_key = Fernet.generate_key().decode("ascii")
    current_key = Fernet.generate_key().decode("ascii")
    old_ciphertext = ProviderAPIKeyCipher(encryption_key=previous_key).encrypt("sk-old")
    cipher = ProviderAPIKeyCipher(
        encryption_key=current_key,
        previous_keys=previous_key,
    )

    rotated = cipher.rotate(old_ciphertext)

    assert cipher.decrypt(old_ciphertext) == "sk-old"
    assert cipher.decrypt(rotated) == "sk-old"
    assert ProviderAPIKeyCipher(encryption_key=current_key).decrypt(rotated) == "sk-old"
    with pytest.raises(SecretCryptoError):
        ProviderAPIKeyCipher(encryption_key=current_key).decrypt(old_ciphertext)


def test_provider_api_key_cipher_rejects_invalid_ciphertext() -> None:
    cipher = ProviderAPIKeyCipher(encryption_key=Fernet.generate_key().decode("ascii"))

    with pytest.raises(SecretCryptoError):
        cipher.decrypt("not-a-fernet-token")
