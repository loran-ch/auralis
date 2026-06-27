"""
LiveTrans — 请求/响应 Pydantic Schema (PRD §4.7.2 ~ §4.7.8)
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, EmailStr


# ─── 请求体 ─────────────────────────────────────────────

class SendCodeRequest(BaseModel):
    """发送验证码 — 手机号或邮箱"""
    target: str = Field(..., min_length=5, max_length=128, description="手机号或邮箱")
    target_type: str = Field(default="phone", pattern="^(phone|email)$")
    scene: str = Field(default="register", pattern="^(register|login)$")


class PhoneRegisterRequest(BaseModel):
    """手机号 + 验证码 注册"""
    phone: str = Field(..., min_length=11, max_length=20)
    code: str = Field(..., min_length=4, max_length=6)
    nickname: Optional[str] = Field(default=None, max_length=64)


class PhoneLoginRequest(BaseModel):
    """手机号 + 验证码 登录"""
    phone: str = Field(..., min_length=11, max_length=20)
    code: str = Field(..., min_length=4, max_length=6)


class EmailRegisterRequest(BaseModel):
    """邮箱 + 密码 注册"""
    email: str = Field(..., max_length=128)
    password: str = Field(..., min_length=6, max_length=20)
    nickname: Optional[str] = Field(default=None, max_length=64)


class EmailLoginRequest(BaseModel):
    """邮箱 + 密码 登录"""
    email: str = Field(..., max_length=128)
    password: str = Field(..., min_length=6, max_length=20)


# ─── 响应体 ─────────────────────────────────────────────

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int             # Access Token 剩余秒数


class UserInfoResponse(BaseModel):
    id: int
    nickname: Optional[str] = None
    avatar_url: Optional[str] = None
    email: Optional[str] = None
    email_verified: bool = False
    phone: Optional[str] = None
    phone_verified: bool = False
    member_level: str = "free"
    status: str = "active"
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class RegisterResponse(BaseModel):
    user: UserInfoResponse
    tokens: TokenResponse
    message: str


class LoginResponse(RegisterResponse):
    pass


class SendCodeResponse(BaseModel):
    message: str
    expires_in: int = 300


class MessageResponse(BaseModel):
    message: str
    detail: Optional[str] = None
