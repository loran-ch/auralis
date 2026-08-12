"""LiveTrans Voice — 管理员审计日志模型"""
from datetime import datetime
from sqlalchemy import Column, BigInteger, String, DateTime, JSON, ForeignKey
from database import Base


class AuditLog(Base):
    __tablename__ = "admin_audit_logs"

    id          = Column(BigInteger, primary_key=True, autoincrement=True)
    admin_id    = Column(BigInteger, ForeignKey("users.id"), nullable=False, comment="执行操作的管理员ID")
    admin_name  = Column(String(64), comment="管理员昵称（冗余快照）")
    action      = Column(String(64), nullable=False, comment="操作类型：user.disable, lecture.delete 等")
    target_type = Column(String(32), comment="目标类型：user, lecture")
    target_id   = Column(BigInteger, comment="目标记录 ID")
    detail      = Column(JSON, comment="变更摘要")
    ip_address  = Column(String(45))
    created_at  = Column(DateTime, default=datetime.utcnow)
