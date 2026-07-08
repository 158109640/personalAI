from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func
from sqlalchemy.orm import selectinload
from app.models.conversation import Conversation, Message
from app.models.user import User
from app.models.message_attachment import MessageAttachment
from typing import List, Dict, Optional

class ConversationService:
    """会话管理服务"""

    @staticmethod
    async def get_or_create_conversation(
        db: AsyncSession,
        user: User,
        conversation_id: Optional[int] = None
    ) -> Conversation:
        """
        获取指定会话，如果不存在则创建新会话
        """
        if conversation_id:
            # 从数据库中获取会话
            stmt = select(Conversation).where(
                Conversation.id == conversation_id,
                Conversation.user_id == user.id
            )
            result = await db.execute(stmt)
            conv = result.scalar_one_or_none()
            if conv:
                return conv

        # 没有会话，创建新的
        print('没有会话，创建新的')
        new_conv = Conversation(user_id=user.id, title="新对话")
        db.add(new_conv)
        await db.commit()
        await db.refresh(new_conv)
        return new_conv
    
    @staticmethod
    async def get_conversation_message_count(
        db: AsyncSession,
        conversation_id: int
    ) -> int:
        """获取会话的消息总数量"""
        stmt = select(func.count(Message.id)).where(
            Message.conversation_id == conversation_id
        )
        result = await db.execute(stmt)
        return result.scalar_one()

    @staticmethod
    async def get_conversation_messages(
        db: AsyncSession,
        conversation_id: int,
        limit: int = 10,
        offset: int = 0
    ) -> List[Dict[str, str]]:
        """获取会话的最新10条消息"""
        stmt = select(func.count()).select_from(Message).where(
            Message.conversation_id == conversation_id
        )
        result = await db.execute(stmt)
        count = result.scalar()  # 直接获取数量

        stmt = (
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .options(selectinload(Message.attachments))
            .order_by(Message.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await db.execute(stmt)
        messages = list(reversed(result.scalars().all()))
        return {
            "data": [
                {
                    "id": msg.id,
                    "role": msg.role,
                    "content": msg.content,
                    "type": msg.type,
                    "attachments": [
                        {
                            "file_url": att.file_url,
                            "file_name": att.file_name,
                            "file_size": att.file_size,
                            "file_type": att.file_type,
                        }
                        for att in msg.attachments
                    ],
                }
                for msg in messages
            ],
            "total": count,
        }

    @staticmethod
    async def add_message(
        db: AsyncSession,
        conversation_id: int,
        role: str,
        content: str,
        files: Optional[List[Dict[str, str]]] = None,
        type: str = "text"
    ) -> Message:
        """添加消息到会话"""
        # 先创建并保存消息（不带 attachments，避免关系赋值错误）
        msg = Message(
            conversation_id=conversation_id,
            role=role,
            content=content,
            type=type
        )
        db.add(msg)
        await db.commit()
        await db.refresh(msg)  # 这会给 msg 分配 id
        
        # 然后再添加附件
        if files:
            for file in files:
                db.add(MessageAttachment(
                    message_id=msg.id,
                    file_url=file["file_url"],
                    file_name=file["file_name"],
                    file_size=file["file_size"],
                    file_type=file["file_type"]
                ))
            await db.commit()
        
        return msg

    @staticmethod
    async def update_conversation_title(
        db: AsyncSession,
        conversation_id: int,
        title: str
    ):
        """更新会话标题"""
        stmt = select(Conversation).where(Conversation.id == conversation_id)
        result = await db.execute(stmt)
        conv = result.scalar_one_or_none()
        if conv:
            conv.title = title
            await db.commit()

    @staticmethod
    async def get_user_conversations(
        db: AsyncSession,
        user: User
    ) -> List[Conversation]:
        """获取用户的所有会话列表"""
        stmt = select(Conversation).where(
            Conversation.user_id == user.id
        ).order_by(desc(Conversation.updated_at))
        result = await db.execute(stmt)
        return result.scalars().all()

conversation_service = ConversationService()