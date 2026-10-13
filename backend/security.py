"""Tasks 1.9 and 1.10: password hashing and JWT authentication."""
import os
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from dotenv import load_dotenv
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

load_dotenv()
TOKEN_ALGORITHM = "HS256"
TOKEN_ISSUER = "omnistat"
bearer_scheme = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    """Store a bcrypt hash, NEVER the original password."""
    raw = password.encode("utf-8")
    if len(raw) > 72:
        raise ValueError("Password must be 72 bytes or fewer")
    return bcrypt.hashpw(raw, bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, stored_hash: str) -> bool:
    """Compare a login password to the hash saved in the database."""
    try:
        return bcrypt.checkpw(password.encode("utf-8"), stored_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def jwt_secret() -> str:
    secret = os.getenv("JWT_SECRET_KEY")
    if not secret or len(secret) < 32 or secret.startswith("replace-with-"):
        raise RuntimeError("Set JWT_SECRET_KEY to a random value of at least 32 characters in .env")
    return secret


def create_access_token(user_id: str, business_id: str) -> str:
    """Issue a signed access token expiring in one hour."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),  # subject = logged-in user ID
        "business_id": str(business_id),
        "iss": TOKEN_ISSUER,
        "iat": now,
        "exp": now + timedelta(hours=1),
    }
    return jwt.encode(payload, jwt_secret(), algorithm=TOKEN_ALGORITHM)


def verify_access_token(token: str) -> dict:
    """Reject expired, invalid, or tampered-with tokens."""
    try:
        claims = jwt.decode(
            token,
            jwt_secret(),
            algorithms=[TOKEN_ALGORITHM],
            issuer=TOKEN_ISSUER,
            options={"require": ["sub", "business_id", "iss", "exp", "iat"]},
        )
        if not claims["sub"] or not claims["business_id"]:
            raise jwt.InvalidTokenError("Missing identity")
        return claims
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")


def get_current_user_claims(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> dict:
    """Reusable FastAPI auth dependency for Nicholas's /api/auth/me endpoint."""
    if credentials is None:
        raise HTTPException(status_code=401, detail="Authorization token required")
    return verify_access_token(credentials.credentials)
