"""LiveTrans Voice — 认证请求/响应 Schema"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class SendCodeReq(BaseModel):
    target: str = Field(..., min_length=5, max_length=128)
    scene: str = Field(default="register", pattern="^(register|login)$")


class RegisterReq(BaseModel):
    phone: str = Field(..., min_length=11, max_length=20)
    code: str = Field(..., min_length=4, max_length=6)
    password: str = Field(..., min_length=6, max_length=20)
    nickname: Optional[str] = Field(default=None, max_length=64)


class LoginReq(BaseModel):
    phone: str = Field(..., min_length=11, max_length=20)
    password: str = Field(..., min_length=6, max_length=20)


class TokenResp(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class UserResp(BaseModel):
    id: int
    nickname: Optional[str] = None
    avatar_url: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    university: Optional[str] = None
    major: Optional[str] = None
    member_level: str = "free"
    created_at: Optional[datetime] = None
    model_config = {"from_attributes": True}


class AuthResp(BaseModel):
    user: UserResp
    tokens: TokenResp
    message: str


class MsgResp(BaseModel):
    message: str
    detail: Optional[str] = None
