# app/services/upload_service.py
import os
import uuid
from datetime import datetime
from fastapi import UploadFile, HTTPException
from app.core.config import settings

class UploadService:
    def __init__(self):
        self.upload_dir = settings.UPLOAD_DIR
        self.base_url = settings.BASE_URL
        self.max_file_size = settings.MAX_FILE_SIZE
    
    async def upload_file(self, file: UploadFile, user_id: int):
        """处理图片上传，返回图片信息"""
        # 1. 生成保存路径
        date_path = datetime.now().strftime("%Y/%m/%d")
        file_ext = os.path.splitext(file.filename)[1]
        filename = f"{uuid.uuid4()}{file_ext}"
        storage_path = f"{self.upload_dir}/images/{user_id}/{date_path}"
        
        # 2. 保存到服务器
        os.makedirs(storage_path, exist_ok=True)
        file_path = os.path.join(storage_path, filename)
        
        content = await file.read()
        with open(file_path, "wb") as f:
            f.write(content)
        
        # 3. 重置文件指针，方便后续再次读取
        await file.seek(0)
        
        # 4. 返回图片信息
        return {
            "url": f"{self.base_url}/uploads/images/{user_id}/{date_path}/{filename}",
            "name": file.filename,
            "size": len(content),
            "type": file.content_type,
            "path": file_path
        }

upload_service = UploadService()