"""Tasks 1.8, 1.11, 1.12: OmniStat FastAPI server and authentication routes."""
import psycopg
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles

from backend.database import get_connection
from backend.schemas import AuthResponse, LoginRequest, RegisterRequest
from backend.security import create_access_token, hash_password, verify_password, jwt_secret
from fastapi import Depends
from backend.schemas import MeResponse
from backend.security import get_current_user_claims

app = FastAPI(title="OmniStat Authentication API")


@app.get("/health")
def health():
    """Simple endpoint to check whether the API server is running."""
    return {"status": "ok"}


@app.post("/api/auth/register", response_model=AuthResponse, status_code=201)
def register(data: RegisterRequest):
    """Create business + user + owner membership as ONE atomic transaction.

    Psycopg's connection context commits only if all statements succeed;
    an exception automatically rolls everything back.
    """
    jwt_secret()  # Check configuration before modifying the database.
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO businesses (name) VALUES (%s) RETURNING id",
                    (data.business_name,),
                )
                business_id = cur.fetchone()[0]

                # Never insert plaintext passwords into the users table.
                password_digest = hash_password(data.password)
                cur.execute(
                    """INSERT INTO users (name, email, password_hash)
                       VALUES (%s, %s, %s) RETURNING id""",
                    (data.name, data.email, password_digest),
                )
                user_id = cur.fetchone()[0]

                cur.execute(
                    """INSERT INTO memberships (user_id, business_id, role)
                       VALUES (%s, %s, %s)""",
                    (user_id, business_id, "owner"),
                )
        # Only return a token AFTER PostgreSQL successfully commits.
        return AuthResponse(
            access_token=create_access_token(str(user_id), str(business_id)),
            user_id=str(user_id),
            business_id=str(business_id),
        )
    except psycopg.errors.UniqueViolation:
        raise HTTPException(status_code=409, detail="Email already registered")


@app.post("/api/auth/login", response_model=AuthResponse)
def login(data: LoginRequest):
    """Find the account, verify bcrypt password, then return a JWT."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT u.id, u.password_hash, m.business_id
                   FROM users AS u
                   JOIN memberships AS m ON m.user_id = u.id
                   WHERE u.email = %s
                   ORDER BY m.created_at ASC, m.id ASC
                   LIMIT 1""",
                (data.email,),
            )
            row = cur.fetchone()

    # Same message for unknown email and wrong password: don't reveal accounts.
    if row is None or not verify_password(data.password, row[1]):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    user_id, _password_hash, business_id = row
    return AuthResponse(
        access_token=create_access_token(str(user_id), str(business_id)),
        user_id=str(user_id),
        business_id=str(business_id),
    )

"""Nicholas - Task 2.3: return logged in user and their business"""
@app.get("/api/auth/me", response_model=MeResponse)
def me(claims: dict = Depends(get_current_user_claims)):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """ SELECT u.name, u.email, b.id, b.name, m.role
                FROM users AS u
                JOIN memberships AS m ON m.user_id = u.id
                JOIN businesses AS b ON b.id = m.business_id
                WHERE u.id = %s AND b.id = %s""",
                (claims["sub"], claims["business_id"]),
            )
            row = cur.fetchone()

    # Valid token, but no matching user or membership
    if row is None:
        raise HTTPException(status_code=401, detail="Account no longer exists")

    user_name, email, business_id, business_name, role = row
    return MeResponse(
        user_id=claims["sub"],
        name=user_name,
        email=email,
        business_id=str(business_id),
        business_name=business_name,
        role=role
    )
# Nicholas - serve the frontend pages from the same server as the API, so the forms' fetch("/api/...") 
# calls reach the backend. MUST stay at the BOTTOM so the /api routes above take priority.
app.mount("/", StaticFiles(directory=".", html=True), name="frontend")