"""LiveTrans Voice — 管理员权限依赖"""
from fastapi import Depends, HTTPException, Request
from models.user import User
from routers.auth import get_current_user


def require_admin(
    request: Request,
    user: User = Depends(get_current_user),
) -> User:
    """平台后台权限：仅 super_admin 可访问。

    ``admin`` 在课堂产品中承担教师角色，不应获得用户、课堂和系统设置的
    平台管理权限。保留此依赖名是为了避免改动既有路由路径。
    """
    if not user:
        raise HTTPException(status_code=401, detail="请先登录")
    if user.role != "super_admin":
        raise HTTPException(status_code=403, detail="需要超级管理员权限")
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
