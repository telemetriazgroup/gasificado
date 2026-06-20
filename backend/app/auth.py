import os
from datetime import datetime, timedelta, timezone
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

SECRET_KEY = os.getenv("JWT_SECRET", "gasificado-jwt-secret-change-in-prod")
ALGORITHM = "HS256"
TOKEN_HOURS = 12

USERS = {
    "admin": {"password": "ProyectoZtrack2026!", "role": "admin"},
    "gasificado": {"password": "gasificado2026", "role": "client"},
}

security = HTTPBearer(auto_error=False)


class User(BaseModel):
    username: str
    role: str


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    token: str
    username: str
    role: str
    expires_at: datetime


def create_token(username: str, role: str) -> LoginResponse:
    expires = datetime.now(timezone.utc) + timedelta(hours=TOKEN_HOURS)
    payload = {
        "sub": username,
        "role": role,
        "exp": expires,
    }
    token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    return LoginResponse(
        token=token,
        username=username,
        role=role,
        expires_at=expires,
    )


def authenticate(username: str, password: str) -> User | None:
    record = USERS.get(username)
    if not record or record["password"] != password:
        return None
    return User(username=username, role=record["role"])


def decode_token(token: str) -> User:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        role = payload.get("role")
        if not username or not role:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido")
        return User(username=username, role=role)
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido") from exc


def _extract_token(
    credentials: HTTPAuthorizationCredentials | None,
    token_query: str | None,
) -> str:
    if credentials and credentials.credentials:
        return credentials.credentials
    if token_query:
        return token_query
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="No autenticado")


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)] = None,
    token: Annotated[str | None, Query(alias="token")] = None,
) -> User:
    raw = _extract_token(credentials, token)
    return decode_token(raw)


def require_admin(user: Annotated[User, Depends(get_current_user)]) -> User:
    if user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Solo administrador")
    return user


def require_client_or_admin(user: Annotated[User, Depends(get_current_user)]) -> User:
    return user
