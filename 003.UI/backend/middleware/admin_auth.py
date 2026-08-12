"""LiveTrans Voice — 管理员权限依赖"""
from fastapi import Depends, HTTPException, Request
from models.user import User
from routers.auth import get_current_user


def require_admin(
    request: Request,
    user: User = Depends(get_current_user),
) -> User:
    """要求登录且角色为 admin 或 super_admin。"""
    if not user:
        raise HTTPException(status_code=401, detail="请先登录")
    if user.role not in ("admin", "super_admin"):
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return user


def require_super_admin(
    request: Request,
    user: User = Depends(get_current_user),
) -> User:
    """要求登录且角色为 super_admin。"""
    if not user:
        raise HTTPException(status_code=401, detail="请先登录")
    if user.role != "super_admin":
        raise HTTPException(status_code=403, detail="需要超级管理员权限")
    return user
