"""
LiveTrans — 认证路由
POST /api/auth/send-code     — 发送验证码
POST /api/auth/register      — 注册 (手机号 or 邮箱)
POST /api/auth/login         — 登录 (手机号 or 邮箱)
GET  /api/auth/me            — 获取当前用户
POST /api/auth/logout        — 退出登录
"""
from fastapi import APIRouter, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from database import get_db
from services.auth import (
    send_verification_code, register_by_phone, register_by_email,
    login_by_phone, login_by_email, revoke_all_tokens,
)
from schemas.auth import (
    SendCodeRequest, SendCodeResponse,
    PhoneRegisterRequest, EmailRegisterRequest,
    PhoneLoginRequest, EmailLoginRequest,
    RegisterResponse, LoginResponse,
    UserInfoResponse, MessageResponse, TokenResponse,
)
from utils.security import get_user_id_from_token, decode_token

router = APIRouter(prefix="/api/auth", tags=["认证"])
security = HTTPBearer(auto_error=False)


# ─── 依赖: 获取当前用户 ─────────────────────────────────

def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db),
):
    """从 Bearer Token 中解析当前用户，未登录返回 None"""
    if not credentials:
        return None
    user_id = get_user_id_from_token(credentials.credentials)
    if not user_id:
        return None
    from models.user import User
    return db.query(User).filter(User.id == user_id).first()


# ─── 路由 ───────────────────────────────────────────────

@router.post("/send-code", response_model=SendCodeResponse)
def send_code(req: SendCodeRequest, request: Request, db: Session = Depends(get_db)):
    """
    POST /api/auth/send-code
    发送验证码 — PRD §4.7.2
    Body: { "target": "138xxxx", "target_type": "phone", "scene": "register" }
    """
    ip = request.client.host if request.client else None
    result = send_verification_code(db, req.target, req.target_type, req.scene, ip)
    if not result["success"]:
        from fastapi import HTTPException
        raise HTTPException(status_code=429, detail=result["message"])
    return SendCodeResponse(
        message=result["message"],
        expires_in=result.get("expires_in", 300),
    )


@router.post("/register-phone", response_model=RegisterResponse)
def register_phone(req: PhoneRegisterRequest, request: Request, db: Session = Depends(get_db)):
    """POST /api/auth/register-phone — 手机号注册"""
    ip = request.client.host if request.client else None
    result = register_by_phone(db, req.phone, req.code, req.nickname, ip)
    if not result["success"]:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail=result["message"])
    user = result["user"]
    tokens = result["tokens"]
    return RegisterResponse(
        user=UserInfoResponse.model_validate(user),
        tokens=TokenResponse(
            access_token=tokens["access_token"],
            refresh_token=tokens["refresh_token"],
            expires_in=7 * 24 * 3600,
        ),
        message=result["message"],
    )


@router.post("/register-email", response_model=RegisterResponse)
def register_email(req: EmailRegisterRequest, request: Request, db: Session = Depends(get_db)):
    """POST /api/auth/register-email — 邮箱注册"""
    ip = request.client.host if request.client else None
    result = register_by_email(db, req.email, req.password, req.nickname, ip)
    if not result["success"]:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail=result["message"])
    user = result["user"]
    tokens = result["tokens"]
    return RegisterResponse(
        user=UserInfoResponse.model_validate(user),
        tokens=TokenResponse(
            access_token=tokens["access_token"],
            refresh_token=tokens["refresh_token"],
            expires_in=7 * 24 * 3600,
        ),
        message=result["message"],
    )


@router.post("/login-phone", response_model=LoginResponse)
def login_phone(req: PhoneLoginRequest, request: Request, db: Session = Depends(get_db)):
    """POST /api/auth/login-phone — 手机号登录"""
    ip = request.client.host if request.client else None
    result = login_by_phone(db, req.phone, req.code, ip)
    if not result["success"]:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail=result["message"])
    user = result["user"]
    tokens = result["tokens"]
    return LoginResponse(
        user=UserInfoResponse.model_validate(user),
        tokens=TokenResponse(
            access_token=tokens["access_token"],
            refresh_token=tokens["refresh_token"],
            expires_in=7 * 24 * 3600,
        ),
        message=result["message"],
    )


@router.post("/login-email", response_model=LoginResponse)
def login_email(req: EmailLoginRequest, request: Request, db: Session = Depends(get_db)):
    """POST /api/auth/login-email — 邮箱登录"""
    ip = request.client.host if request.client else None
    result = login_by_email(db, req.email, req.password, ip)
    if not result["success"]:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail=result["message"])
    user = result["user"]
    tokens = result["tokens"]
    return LoginResponse(
        user=UserInfoResponse.model_validate(user),
        tokens=TokenResponse(
            access_token=tokens["access_token"],
            refresh_token=tokens["refresh_token"],
            expires_in=7 * 24 * 3600,
        ),
        message=result["message"],
    )


@router.get("/me", response_model=UserInfoResponse)
def get_me(current_user=Depends(get_current_user)):
    """
    GET /api/auth/me
    获取当前登录用户信息 — 需要 Bearer Token
    """
    if not current_user:
        from fastapi import HTTPException
        raise HTTPException(status_code=401, detail="未登录")
    return UserInfoResponse.model_validate(current_user)


@router.post("/logout", response_model=MessageResponse)
def logout(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    """
    POST /api/auth/logout
    退出登录 — 撤销所有 Token — PRD §4.7.3
    """
    if not current_user:
        from fastapi import HTTPException
        raise HTTPException(status_code=401, detail="未登录")
    revoke_all_tokens(db, current_user.id)
    return MessageResponse(message="已退出登录", detail="所有设备 Token 已失效")
