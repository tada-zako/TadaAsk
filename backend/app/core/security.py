from datetime import datetime, timezone, timedelta

import jwt
from pwdlib import PasswordHash

from .config import settings

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
