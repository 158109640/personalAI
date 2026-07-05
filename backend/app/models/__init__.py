# 这行代码的作用是把 user.py 和 document.py 里的模型类暴露到 models 这个包的顶层
# 这样你就可以直接 from app.models import User, Document，而不需要写 from app.models.user import User
from .user import User
from .document import Document
from .conversation import Conversation, Message
from .message_attachment import MessageAttachment
