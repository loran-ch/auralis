"""LiveTrans Voice — 认证请求/响应 Schema"""
import re
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, field_validator, model_validator


def _normalize_phone(value: str) -> str:
    value = value.strip().replace(" ", "").replace("-", "")
    if len(value) == 11 and value.startswith("1"):
        return f"+86{value}"
    return value


def _validate_bcrypt_password(value: str) -> str:
    if len(value.encode("utf-8")) > 72:
        raise ValueError("密码的 UTF-8 编码不能超过 72 字节")
    return value


class SendCodeReq(BaseModel):
    target: str = Field(..., pattern=r"^\+?\d{11,15}$")
    scene: str = Field(default="register", pattern="^(register|login)$")

    @field_validator("target", mode="before")
    @classmethod
    def normalize_target(cls, value: str) -> str:
        return _normalize_phone(value)


class RegisterReq(BaseModel):
    username: str = Field(..., min_length=3, max_length=32, pattern=r"^[a-zA-Z0-9_]+$")
    phone: str = Field(..., pattern=r"^\+?\d{11,15}$")
    code: str = Field(..., min_length=4, max_length=6)
    password: str = Field(..., min_length=6, max_length=72)
    nickname: Optional[str] = Field(default=None, max_length=64)

    @field_validator("phone", mode="before")
    @classmethod
    def normalize_phone(cls, value: str) -> str:
        return _normalize_phone(value)

    @field_validator("nickname")
    @classmethod
    def normalize_nickname(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        return value.strip() or None

    @field_validator("password")
    @classmethod
    def validate_password_bytes(cls, value: str) -> str:
        return _validate_bcrypt_password(value)


class LoginReq(BaseModel):
    account: str = Field(..., min_length=1, max_length=128)
    password: str = Field(..., min_length=6, max_length=72)

    @field_validator("account", mode="before")
    @classmethod
    def normalize_account(cls, value: str) -> str:
        compact = value.strip().replace(" ", "").replace("-", "")
        if re.match(r"^1[3-9]\d{9}$", compact):
            return f"+86{compact}"
        return value.strip()

    @field_validator("password")
    @classmethod
    def validate_password_bytes(cls, value: str) -> str:
        return _validate_bcrypt_password(value)


class RefreshReq(BaseModel):
    refresh_token: str = Field(..., min_length=20, max_length=1024)


class ChangePasswordReq(BaseModel):
    current_password: str = Field(..., min_length=6, max_length=72)
    new_password: str = Field(..., min_length=6, max_length=72)

    @field_validator("current_password", "new_password")
    @classmethod
    def validate_password_bytes(cls, value: str) -> str:
        return _validate_bcrypt_password(value)

    @model_validator(mode="after")
    def passwords_must_differ(self):
        if self.current_password == self.new_password:
            raise ValueError("新密码不能与当前密码相同")
        return self


class TokenResp(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class UserResp(BaseModel):
    id: int
    nickname: Optional[str] = None
    username: Optional[str] = None
    avatar_url: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    university: Optional[str] = None
    major: Optional[str] = None
    focus_area: Optional[str] = None
    member_level: str = "free"
    role: str = "user"
    created_at: Optional[datetime] = None
    model_config = {"from_attributes": True}


class AuthResp(BaseModel):
    user: UserResp
    tokens: TokenResp
    message: str


class MsgResp(BaseModel):
    message: str
    detail: Optional[str] = None
