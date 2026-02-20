from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID

from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel
import os

SECRET_KEY = os.getenv(
    "JWT_SECRET_KEY", "your-secret-key-change-in-production-use-env-variable"
)
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30 * 24  # 30 days

pwd_context = CryptContext(
    schemes=["bcrypt"], deprecated="auto", bcrypt__truncate_error=True
)


class TokenData(BaseModel):
    email: Optional[str] = None
    user_id: Optional[str] = None
    tenant_id: Optional[str] = None  # None for super_admin
    tenant_code: Optional[str] = None
    role: Optional[str] = None
    scope: Optional[str] = None  # "platform" | "tenant"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=15))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def verify_token(token: str) -> Optional[TokenData]:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        user_id: str = payload.get("user_id")
        tenant_id: str = payload.get("tenant_id")
        tenant_code: str = payload.get("tenant_code")
        role: str = payload.get("role")
        scope: str = payload.get("scope", "tenant")
        if email is None:
            return None
        return TokenData(
            email=email, user_id=user_id, tenant_id=tenant_id,
            tenant_code=tenant_code, role=role, scope=scope,
        )
    except JWTError:
        return None
