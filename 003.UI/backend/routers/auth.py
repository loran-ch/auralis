"""LiveTrans Voice — 认证路由"""
from typing import Optional
import uuid
from pathlib import Path
from fastapi import APIRouter, Depends, Request, HTTPException, UploadFile, File
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field, model_validator
from sqlalchemy.orm import Session

from config import ACCESS_EXPIRE_MINUTES, MAX_AVATAR_SIZE_MB
from database import get_db
from models.user import User
from services.auth import (send_code, register, login, revoke_all_tokens,
                           authenticate_access_token, refresh_tokens,
                           revoke_token, change_password)
from services.preferences import refresh_user_stats
from services.registration import registration_is_enabled
from services.captcha import create_registration_captcha
from schemas.auth import (ChangePasswordReq, SendCodeReq, RegisterReq, LoginReq, RefreshReq,
                          AuthResp, TokenResp, UserResp, MsgResp,
                          RegistrationStatusResp, CaptchaResp)
from schemas.preferences import UserStatsResp

router = APIRouter(prefix="/api/auth", tags=["认证"])
security = HTTPBearer(auto_error=False)


@router.get("/registration-status", response_model=RegistrationStatusResp)
def api_registration_status(db: Session = Depends(get_db)):
    enabled = registration_is_enabled(db)
    return RegistrationStatusResp(
        enabled=enabled,
        message="当前允许新用户注册" if enabled else "管理员已暂停新用户注册",
    )


@router.get("/captcha", response_model=CaptchaResp)
def api_registration_captcha(db: Session = Depends(get_db)):
    if not registration_is_enabled(db):
        raise HTTPException(status_code=403, detail="管理员已暂停新用户注册")
    return CaptchaResp(**create_registration_captcha(db))


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db),
) -> Optional[User]:
    if not credentials:
        return None
    return authenticate_access_token(db, credentials.credentials)


@router.post("/send-code", response_model=MsgResp)
def api_send_code(req: SendCodeReq, request: Request, db: Session = Depends(get_db)):
    if req.scene == "register" and not registration_is_enabled(db):
        raise HTTPException(status_code=403, detail="管理员已暂停新用户注册")
    ip = request.client.host if request.client else None
    result = send_code(db, req.target, req.scene, ip)
    if not result["success"]:
        raise HTTPException(status_code=429, detail=result["message"])
    return MsgResp(message=result["message"], detail=f"{result['expires_in']}秒内有效")


@router.post("/register", response_model=AuthResp)
def api_register(req: RegisterReq, request: Request, db: Session = Depends(get_db)):
    if not registration_is_enabled(db):
        raise HTTPException(status_code=403, detail="管理员已暂停新用户注册")
    ip = request.client.host if request.client else None
    result = register(
        db,
        req.username,
        req.password,
        req.nickname,
        req.captcha_token,
        req.captcha_code,
        ip,
        req.phone,
    )
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    u = result["user"]
    t = result["tokens"]
    return AuthResp(
        user=UserResp.model_validate(u),
        tokens=TokenResp(access_token=t["access_token"], refresh_token=t["refresh_token"],
                         expires_in=ACCESS_EXPIRE_MINUTES * 60),
        message=result["message"],
    )


@router.post("/login", response_model=AuthResp)
def api_login(req: LoginReq, request: Request, db: Session = Depends(get_db)):
    ip = request.client.host if request.client else None
    result = login(db, req.account, req.password, ip)
    if not result["success"]:
        raise HTTPException(status_code=401, detail=result["message"])
    u = result["user"]
    t = result["tokens"]
    return AuthResp(
        user=UserResp.model_validate(u),
        tokens=TokenResp(access_token=t["access_token"], refresh_token=t["refresh_token"],
                         expires_in=ACCESS_EXPIRE_MINUTES * 60),
        message=result["message"],
    )


@router.post("/refresh", response_model=AuthResp)
def api_refresh(req: RefreshReq, request: Request, db: Session = Depends(get_db)):
    ip = request.client.host if request.client else None
    result = refresh_tokens(db, req.refresh_token, ip)
    if not result["success"]:
        raise HTTPException(status_code=401, detail=result["message"])
    u = result["user"]
    t = result["tokens"]
    return AuthResp(
        user=UserResp.model_validate(u),
        tokens=TokenResp(access_token=t["access_token"], refresh_token=t["refresh_token"],
                         expires_in=ACCESS_EXPIRE_MINUTES * 60),
        message=result["message"],
    )


@router.get("/me", response_model=UserResp)
def api_me(user: User = Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=401, detail="未登录")
    return UserResp.model_validate(user)


@router.post("/logout", response_model=MsgResp)
def api_logout(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not user or not credentials:
        raise HTTPException(status_code=401, detail="未登录")
    revoke_token(db, user.id, credentials.credentials)
    return MsgResp(message="已退出登录")


@router.post("/logout-all", response_model=MsgResp)
def api_logout_all(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not user:
        raise HTTPException(status_code=401, detail="未登录")
    revoke_all_tokens(db, user.id)
    return MsgResp(message="所有设备均已退出登录")


@router.put("/password", response_model=MsgResp)
def api_change_password(request: ChangePasswordReq,
                        user: User = Depends(get_current_user),
                        db: Session = Depends(get_db)):
    if not user:
        raise HTTPException(status_code=401, detail="未登录")
    result = change_password(
        db, user, request.current_password, request.new_password
    )
    if not result["success"]:
        raise HTTPException(400, result["message"])
    return MsgResp(message=result["message"])


# ─── 头像上传 ─────────────────────────────────────────
UPLOAD_DIR = Path(__file__).resolve().parent.parent.parent / "frontend" / "uploads" / "avatars"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def _remove_local_avatar(avatar_url: Optional[str]) -> None:
    if not avatar_url or not avatar_url.startswith("/uploads/avatars/"):
        return
    candidate = (UPLOAD_DIR / Path(avatar_url).name).resolve()
    if candidate.parent == UPLOAD_DIR.resolve():
        candidate.unlink(missing_ok=True)


def _detect_image_extension(contents: bytes) -> Optional[str]:
    """根据文件签名识别格式，避免仅信任客户端提供的扩展名。"""
    if contents.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if contents.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if contents.startswith((b"GIF87a", b"GIF89a")):
        return ".gif"
    if len(contents) >= 12 and contents[:4] == b"RIFF" and contents[8:12] == b"WEBP":
        return ".webp"
    return None


@router.post("/avatar")
async def api_upload_avatar(file: UploadFile = File(...),
                            user: User = Depends(get_current_user),
                            db: Session = Depends(get_db)):
    if not user:
        raise HTTPException(status_code=401, detail="请先登录")

    # 限制大小
    contents = await file.read()
    if not contents:
        raise HTTPException(status_code=400, detail="图片内容为空")
    if len(contents) > MAX_AVATAR_SIZE_MB * 1024 * 1024:
        raise HTTPException(status_code=413, detail=f"图片不能超过 {MAX_AVATAR_SIZE_MB}MB")
    ext = _detect_image_extension(contents)
    if not ext:
        raise HTTPException(status_code=400, detail="仅支持 JPG/PNG/GIF/WEBP 格式")

    # 保存文件
    filename = f"{user.id}_{uuid.uuid4().hex[:8]}{ext}"
    filepath = UPLOAD_DIR / filename
    filepath.write_bytes(contents)

    # 更新数据库
    old_avatar_url = user.avatar_url
    avatar_url = f"/uploads/avatars/{filename}"
    user.avatar_url = avatar_url
    try:
        db.commit()
    except Exception:
        db.rollback()
        filepath.unlink(missing_ok=True)
        raise
    if old_avatar_url != avatar_url:
        _remove_local_avatar(old_avatar_url)

    return {"avatar_url": avatar_url, "message": "头像上传成功"}


# ─── 更新资料 ─────────────────────────────────────────
class UpdateProfileReq(BaseModel):
    nickname: Optional[str] = Field(None, min_length=1, max_length=64)
    university: Optional[str] = Field(None, max_length=256)
    major: Optional[str] = Field(None, max_length=256)
    focus_area: Optional[str] = Field(None, max_length=256)

    @model_validator(mode="after")
    def require_a_field(self):
        if not self.model_fields_set:
            raise ValueError("至少提供一个需要更新的字段")
        return self


@router.put("/profile")
def api_update_profile(req: UpdateProfileReq,
                       user: User = Depends(get_current_user),
                       db: Session = Depends(get_db)):
    if not user:
        raise HTTPException(status_code=401, detail="请先登录")
    values = req.model_dump(exclude_unset=True)
    for field, value in values.items():
        value = value.strip() if isinstance(value, str) else value
        if field == "nickname" and not value:
            raise HTTPException(status_code=400, detail="名称不能为空")
        setattr(user, field, value or None)
    db.commit()
    db.refresh(user)
    return {
        "user": UserResp.model_validate(user).model_dump(mode="json"),
        "nickname": user.nickname,
        "message": "资料已更新",
    }


# ─── 用户统计 ─────────────────────────────────────────
@router.get("/stats", response_model=UserStatsResp)
def api_user_stats(user: User = Depends(get_current_user),
                   db: Session = Depends(get_db)):
    if not user:
        raise HTTPException(status_code=401, detail="请先登录")

    return UserStatsResp(**refresh_user_stats(db, user.id))
