"""LiveTrans Voice — 认证路由"""
from typing import Optional
from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from database import get_db
from models.user import User
from services.auth import send_code, register, login, revoke_all_tokens
from schemas.auth import (SendCodeReq, RegisterReq, LoginReq,
                          AuthResp, TokenResp, UserResp, MsgResp)
from utils.security import get_user_id_from_token

router = APIRouter(prefix="/api/auth", tags=["认证"])
security = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db),
) -> Optional[User]:
    if not credentials:
        return None
    uid = get_user_id_from_token(credentials.credentials)
    return db.query(User).filter(User.id == uid).first() if uid else None


@router.post("/send-code", response_model=MsgResp)
def api_send_code(req: SendCodeReq, request: Request, db: Session = Depends(get_db)):
    ip = request.client.host if request.client else None
    result = send_code(db, req.target, req.scene, ip)
    if not result["success"]:
        raise HTTPException(status_code=429, detail=result["message"])
    return MsgResp(message=result["message"], detail=f"{result['expires_in']}秒内有效")


@router.post("/register", response_model=AuthResp)
def api_register(req: RegisterReq, request: Request, db: Session = Depends(get_db)):
    ip = request.client.host if request.client else None
    result = register(db, req.phone, req.code, req.password, req.nickname, ip)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    u = result["user"]
    t = result["tokens"]
    return AuthResp(
        user=UserResp.model_validate(u),
        tokens=TokenResp(access_token=t["access_token"], refresh_token=t["refresh_token"],
                         expires_in=7 * 24 * 3600),
        message=result["message"],
    )


@router.post("/login", response_model=AuthResp)
def api_login(req: LoginReq, request: Request, db: Session = Depends(get_db)):
    ip = request.client.host if request.client else None
    result = login(db, req.phone, req.password, ip)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    u = result["user"]
    t = result["tokens"]
    return AuthResp(
        user=UserResp.model_validate(u),
        tokens=TokenResp(access_token=t["access_token"], refresh_token=t["refresh_token"],
                         expires_in=7 * 24 * 3600),
        message=result["message"],
    )


@router.get("/me", response_model=UserResp)
def api_me(user: User = Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=401, detail="未登录")
    return UserResp.model_validate(user)


@router.post("/logout", response_model=MsgResp)
def api_logout(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not user:
        raise HTTPException(status_code=401, detail="未登录")
    revoke_all_tokens(db, user.id)
    return MsgResp(message="已退出登录")
