"""Siddartha - Sprint 2: sales dashboard, business team and employee invites.

Routes deliberately kept in a separate APIRouter to minimize conflicts with
Junior's authentication and Nicholas's existing FastAPI routes.

Requires the additive migration migrations/003_siddartha_sprint2.sql.
"""
from datetime import datetime, timezone
from decimal import Decimal
from secrets import token_urlsafe
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.staticfiles import StaticFiles
from starlette.responses import Response
from pydantic import BaseModel, Field, field_validator

from backend.database import get_connection
from backend.security import get_current_user_claims

router = APIRouter(tags=["Sprint 2 — Siddartha"])


class FrontendOnlyStaticFiles(StaticFiles):
    """Do not accidentally publish .env, SQL files, Python source, or tests.

    Original project mounted the entire repo as public static content.
    Restrict public content to frontend file types, at root or assets/.
    """
    _extensions = {".html", ".css", ".js", ".svg", ".png", ".jpg", ".jpeg", ".ico", ".webp", ".woff", ".woff2"}

    async def get_response(self, path, scope):
        clean = path.strip("/")
        parts = clean.replace("\\", "/").split("/")
        if (not clean or any(not p or p.startswith(".") for p in parts)
                or (len(parts) > 1 and parts[0] not in {"assets", "static"})
                or not any(clean.lower().endswith(ext) for ext in self._extensions)):
            return Response(status_code=404)
        return await super().get_response(path, scope)


class BusinessUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=255)

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Business name cannot be blank")
        return value


class InviteCreate(BaseModel):
    # US4 invites only employees. More roles require an approved access policy.
    role: str = "employee"
    expires_in_days: int = Field(default=7, ge=1, le=30)

    @field_validator("role")
    @classmethod
    def employees_only(cls, role: str) -> str:
        if role != "employee":
            raise ValueError("Only employee invitations are supported")
        return role


def current_member(claims: dict = Depends(get_current_user_claims)) -> dict:
    """Verify the JWT's business membership *against the database* each request.

    A valid token alone is insufficient: a removed employee's old JWT must not
    authorize any business endpoint.
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT m.role FROM memberships AS m
                   JOIN businesses AS b ON b.id = m.business_id
                   WHERE m.user_id = %s AND m.business_id = %s""",
                (claims["sub"], claims["business_id"]),
            )
            membership = cur.fetchone()
    if membership is None:
        raise HTTPException(status_code=403, detail="No access to this business")
    return {
        "user_id": claims["sub"],
        "business_id": claims["business_id"],
        "role": membership[0],
    }


def current_owner(member: dict = Depends(current_member)) -> dict:
    if member["role"] != "owner":
        raise HTTPException(status_code=403, detail="Business owner access required")
    return member


def as_money(value: Decimal) -> float:
    """Return JSON numbers for frontend charting; PostgreSQL computes in NUMERIC."""
    return float(value)


# 3.6 — Contract proposal; Nicholas must coordinate matching dashboard.js keys.
@router.get("/api/dashboard/summary")
def dashboard_summary(member: dict = Depends(current_member)):
    """Business-scoped last 30 calendar days, including zero-revenue dates.

    KPIs are sums for the SAME window as the revenue chart, not lifetime sums.
    The business is selected exclusively from the verified JWT membership.
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT d.day::date,
                          COALESCE(a.total_revenue, 0),
                          COALESCE(a.total_profit, 0),
                          COALESCE(a.items_sold_count, 0),
                          (a.business_id IS NOT NULL)
                   FROM generate_series(
                       CURRENT_DATE - INTERVAL '29 days',
                       CURRENT_DATE, INTERVAL '1 day'
                   ) AS d(day)
                   LEFT JOIN daily_sales_aggregates AS a
                     ON a.business_id = %s AND a.business_date = d.day::date
                   ORDER BY d.day""",
                (member["business_id"],),
            )
            rows = cur.fetchall()
    revenue = sum((r[1] for r in rows), Decimal("0"))
    profit = sum((r[2] for r in rows), Decimal("0"))
    items_sold = sum(r[3] for r in rows)
    return {
        "period": "last_30_days",
        "has_data": any(r[4] for r in rows),
        "kpis": {
            "total_revenue": as_money(revenue),
            "total_profit": as_money(profit),
            "items_sold_count": items_sold,
        },
        "revenue_30_days": [
            {"date": r[0].isoformat(), "revenue": as_money(r[1])} for r in rows
        ],
    }


# 4.5 — Business information and team list (owner restricted).
@router.get("/api/business/team")
def business_team(owner: dict = Depends(current_owner)):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT u.id, u.name, u.email, m.role
                   FROM memberships AS m
                   JOIN users AS u ON u.id = m.user_id
                   WHERE m.business_id = %s
                   ORDER BY u.name, u.id""",
                (owner["business_id"],),
            )
            rows = cur.fetchall()
    return {"business_id": owner["business_id"],
            "members": [
                {"user_id": str(r[0]), "name": r[1], "email": r[2], "role": r[3]}
                for r in rows
            ]}


@router.patch("/api/business")
def update_business(data: BusinessUpdate, owner: dict = Depends(current_owner)):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE businesses SET name = %s
                   WHERE id = %s RETURNING id, name""",
                (data.name, owner["business_id"]),
            )
            row = cur.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Business not found")
    return {"business_id": str(row[0]), "name": row[1]}


# 4.6 — Invitation create and public code validation for US4 signup.
@router.post("/api/invites", status_code=status.HTTP_201_CREATED)
def create_invite(data: InviteCreate, owner: dict = Depends(current_owner)):
    code = token_urlsafe(24)  # unpredictable, URL-safe, 192 bits of entropy
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO invites
                       (business_id, created_by, code, role, expires_at)
                   VALUES (%s, %s, %s, 'employee',
                           CURRENT_TIMESTAMP + (%s * INTERVAL '1 day'))
                   RETURNING expires_at""",
                (owner["business_id"], owner["user_id"], code, data.expires_in_days),
            )
            (expires_at,) = cur.fetchone()
    return {
        "code": code,
        "invite_url": f"signup.html?invite={code}",
        "business_id": owner["business_id"],
        "role": "employee",
        "expires_at": expires_at.isoformat(),
    }


@router.get("/api/invites/{code}")
def invite_details(code: str):
    # No Authorization header: this is used BEFORE an invited employee signs up.
    if len(code) > 64 or not code:
        raise HTTPException(status_code=404, detail="Invitation not found")
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT b.name, i.role, i.expires_at, i.used_at
                   FROM invites AS i JOIN businesses AS b ON b.id = i.business_id
                   WHERE i.code = %s""",
                (code,),
            )
            row = cur.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Invitation not found")
    business_name, role, expires_at, used_at = row
    if used_at is not None or expires_at <= datetime.now(timezone.utc):
        raise HTTPException(status_code=410, detail="Invitation expired or already used")
    return {"business_name": business_name, "role": role,
            "expires_at": expires_at.isoformat(), "valid": True}


# 4.8 — Revokes only the target business membership; does not delete user.
@router.delete("/api/business/team/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_employee(user_id: UUID, owner: dict = Depends(current_owner)):
    if str(user_id) == owner["user_id"]:
        raise HTTPException(status_code=403, detail="Cannot remove yourself")
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT role FROM memberships
                   WHERE user_id = %s AND business_id = %s FOR UPDATE""",
                (user_id, owner["business_id"]),
            )
            row = cur.fetchone()
            if row is None:
                raise HTTPException(status_code=404, detail="Team member not found")
            if row[0] != "employee":
                raise HTTPException(status_code=403, detail="Only employees can be removed")
            cur.execute(
                """DELETE FROM memberships
                   WHERE user_id = %s AND business_id = %s""",
                (user_id, owner["business_id"]),
            )
    return None
