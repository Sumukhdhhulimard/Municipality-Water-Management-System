
import os
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jwt.exceptions import InvalidTokenError
from pwdlib import PasswordHash

password_hasher = PasswordHash.recommended()
security = HTTPBearer()

SECRET = os.getenv("JWT_SECRET", "")
ALGORITHM = "HS256"

def hash_password(password):
    return password_hasher.hash(password)

def verify_password(password, stored_hash):
    try:
        return password_hasher.verify(password, stored_hash)
    except Exception:
        return False

def create_token(user_id, role):
    if len(SECRET) < 32:
        raise RuntimeError("Configure a secure JWT_SECRET")

    expiry = datetime.now(timezone.utc) + timedelta(
        minutes=int(os.getenv("JWT_EXPIRE_MINUTES", "120"))
    )
    return jwt.encode(
        {"sub": str(user_id), "role": role, "exp": expiry},
        SECRET,
        algorithm=ALGORITHM
    )

def current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    try:
        payload = jwt.decode(
            credentials.credentials,
            SECRET,
            algorithms=[ALGORITHM]
        )
        user_id = int(payload["sub"])
        role = payload["role"]

        if role not in ("resident", "operator"):
            raise ValueError("Invalid role")

        return {"id": user_id, "role": role}
    except (InvalidTokenError, ValueError, KeyError):
        raise HTTPException(401, "Invalid or expired token")

def require_role(role):
    def check(user=Depends(current_user)):
        if user["role"] != role:
            raise HTTPException(403, "Access denied")
        return user
    return check
