"""Validate incoming JSON so malformed requests do not reach the database."""
from pydantic import BaseModel, EmailStr, Field, field_validator


class RegisterRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    business_name: str = Field(min_length=1, max_length=255)
    email: EmailStr
    password: str = Field(min_length=8)

    @field_validator("name", "business_name")
    @classmethod
    def nonblank_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Cannot be blank")
        return value

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.lower()

    @field_validator("password")
    @classmethod
    def bcrypt_limit(cls, value: str) -> str:
        if len(value.encode("utf-8")) > 72:
            raise ValueError("Password must be 72 bytes or fewer")
        return value


class LoginRequest(BaseModel):
    email: EmailStr
    password: str

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.lower()


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    business_id: str



"""Nicholas - Task 2.3: who is logged in, for the navbar"""
class MeResponse(BaseModel):
    user_id: str
    name: str
    email: str
    business_id: str
    business_name: str
    role: str