from datetime import datetime, timezone, timedelta

import jwt
from pwdlib import PasswordHash
from cryptography.fernet import MultiFernet, InvalidToken, Fernet

from .exceptions import SecretKeyNotConfiguredError, SecretCryptoError
from .config import settings

# TODO: 后续将用户 auth 相关实现封装到单独的类中
# 密码哈希器
password_hash = PasswordHash.recommended()


def verify_password(plain_pwd: str, hashed_pwd: str) -> bool:
    """验证明文密码与哈希密码是否匹配"""
    return password_hash.verify(plain_pwd, hashed_pwd)


def get_password_hash(password: str) -> str:
    """生成密码哈希"""
    return password_hash.hash(password)


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    """创建 JWT 访问令牌"""
    to_encode = data.copy()

    # 设置令牌过期时间
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=settings.jwt_access_token_expire_minutes
        )

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(
        to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm
    )
    return encoded_jwt


def decode_access_token(token: str) -> dict | None:
    """解码 JWT 访问令牌：返回数据字典或 None（如果无效）"""
    try:
        payload = jwt.decode(
            token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm]
        )
        return payload
    except jwt.PyJWTError:
        return None


class ProviderAPIKeyCipher:
    """API Key 加密和解密工具类"""

    def __init__(self, *, encryption_key: str, previous_keys: str = ""):
        """支持主密钥和多个历史密钥（用于密钥轮换，解密旧数据）"""
        if not encryption_key:
            raise SecretKeyNotConfiguredError(
                "PROVIDER_API_KEY_ENCRYPTION_KEY is not configured."
            )

        raw_keys = [encryption_key]
        raw_keys.extend(key.strip() for key in previous_keys.split(",") if key.strip())

        try:
            self._fernet = MultiFernet(
                [Fernet(key.encode("utf-8")) for key in raw_keys]
            )
        except Exception as e:
            raise SecretCryptoError("Invalid provider API key encryption key.") from e

    def encrypt(self, plaintext: str | None) -> str | None:
        """加密明文 API Key"""
        if plaintext is None or plaintext == "":
            return None

        return self._fernet.encrypt(plaintext.encode("utf-8")).decode("utf-8")

    def decrypt(self, ciphertext: str | None) -> str | None:
        """解密密文 API Key"""
        if ciphertext is None or ciphertext == "":
            return None

        try:
            return self._fernet.decrypt(ciphertext.encode("utf-8")).decode("utf-8")
        except InvalidToken:
            raise SecretCryptoError("Invalid provider API key token.")

    def rotate(self, ciphertext: str | None) -> str | None:
        """使用新的主密钥加密明文 API Key（用于密钥轮换）"""
        plaintext = self.decrypt(ciphertext)
        return self.encrypt(plaintext)
