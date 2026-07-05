from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, BigInteger
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.core.database import Base

class MessageAttachment(Base):
    __tablename__ = "message_attachments"
    
    id = Column(Integer, primary_key=True, index=True)
    message_id = Column(Integer, ForeignKey("messages.id", ondelete="CASCADE"), nullable=False)
    file_url = Column(String(500), nullable=False)
    file_name = Column(String(255), nullable=False)
    file_size = Column(BigInteger, nullable=False)  # 文件大小（字节）
    file_type = Column(String(100), nullable=False)  # MIME类型，如 image/jpeg
    storage_path = Column(String(500), nullable=True)  # 存储路径（可选）
    created_at = Column(DateTime, server_default=func.now())
    
    # 添加反向关系！
    message = relationship("Message", back_populates="attachments")