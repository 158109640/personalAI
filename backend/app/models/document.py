from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base
import enum

class DocumentStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSED = "processed"
    FAILED = "failed"

class Document(Base):
  __tablename__ = "documents"

  id = Column(Integer, primary_key=True, index=True)
  doc_id = Column(String(50), unique=True, index=True, nullable=False)
  filename = Column(String(255), nullable=False)
  collection_name = Column(String(100), nullable=True)
  file_path = Column(String(500), nullable=False)
  content = Column(Text)  # 提取的文本内容
  status = Column(Enum(DocumentStatus), default=DocumentStatus.PENDING)
  created_at = Column(DateTime(timezone=True), server_default=func.now())
  updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
  owner_id = Column(Integer, ForeignKey("users.id"))
  owner = relationship("User", back_populates="documents")