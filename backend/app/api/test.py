# backend/app/api/test_llamaindex.py
from fastapi import APIRouter, Form, File, UploadFile, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.utils.dependencies import get_current_user
from app.models.user import User
from app.models.document import Document
from sqlalchemy import select

router = APIRouter(prefix="/test/llamaindex", tags=["测试-LlamaIndex"])

@router.post("/upload")
async def test_llamaindex_upload(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    使用 LlamaIndex 上传并索引文档（不影响现有功能）
    """
    import uuid
    import os
    import shutil
    
    from app.services.rag_llamaindex import rag_llamaindex_service
    
    try:
        # 生成文档 ID
        doc_id = f"{current_user.id}_{uuid.uuid4().hex[:8]}"
        
        # 保存文件到临时目录
        upload_dir = "./uploads_test"
        os.makedirs(upload_dir, exist_ok=True)
        file_path = os.path.join(upload_dir, f"{doc_id}_{file.filename}")
        
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # 使用 LlamaIndex 创建向量存储
        texts = rag_llamaindex_service.load_document(file_path, file.filename)
        collection_name = rag_llamaindex_service.create_vector_store(
            doc_id=doc_id,
            texts=texts,
            filename=file.filename
        )
        
        # 也可以保存到数据库（可选）
        # 这里我们只返回结果，不影响主数据库
        
        return {
            "success": True,
            "doc_id": doc_id,
            "filename": file.filename,
            "chunks": len(texts),
            "collection_name": collection_name,
            "message": "LlamaIndex 索引创建成功"
        }
        
    except Exception as e:
        import traceback
        raise HTTPException(
            status_code=500,
            detail={
                "error": str(e),
                "traceback": traceback.format_exc()
            }
        )

@router.get("/debug/collections")
async def debug_collections():
    """查看 LlamaIndex 中的所有集合"""
    try:
        from app.services.rag_llamaindex import rag_llamaindex_service
        
        # 获取所有集合
        collections = rag_llamaindex_service.chroma_client.list_collections()
        
        result = []
        for col in collections:
            # 获取集合中的文档数量
            count = col.count()
            result.append({
                "name": col.name,
                "count": count
            })
        
        return {
            "success": True,
            "collections": result
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }        


@router.get("/search")
async def test_llamaindex_search(
    query: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    测试 LlamaIndex 检索（不影响现有功能）
    """
    try:
        from app.services.rag_llamaindex import rag_llamaindex_service
        
        # 1. 获取用户的文档
        stmt = select(Document).where(
            Document.owner_id == current_user.id,
            Document.status == "processed"
        )
        result = await db.execute(stmt)
        docs = result.scalars().all()
        
        if not docs:
            return {
                "success": False,
                "message": "没有找到文档"
            }
        
        doc_ids = [doc.doc_id for doc in docs]
        
        # 2. 路由文档
        target_docs = await rag_llamaindex_service.route_documents(doc_ids, query)
        
        if not target_docs:
            target_docs = doc_ids[:2]
        
        # 3. 执行检索
        chunks = await rag_llamaindex_service.search_all_documents(
            doc_ids=target_docs,
            query=query,
            top_k=5,
            similarity_cutoff=0.2
        )
        
        return {
            "success": True,
            "query": query,
            "doc_ids": doc_ids,
            "target_docs": target_docs,
            "chunks": chunks,
            "chunk_count": len(chunks),
            "research_result": "\n\n".join([chunk["content"] for chunk in chunks]) if chunks else ""
        }
        
    except Exception as e:
        import traceback
        return {
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }


@router.get("/status")
async def test_llamaindex_status():
    """
    检查 LlamaIndex 服务状态
    """
    try:
        from app.services.rag_llamaindex import rag_llamaindex_service
        return {
            "success": True,
            "message": "LlamaIndex 服务已加载",
            "service": str(rag_llamaindex_service)
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


@router.post("/reindex")
async def test_llamaindex_reindex(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    使用 LlamaIndex 重新索引所有文档（不影响现有 rag_service）
    """
    try:
        from app.services.rag_llamaindex import rag_llamaindex_service
        import os
        
        # 1. 获取用户的文档
        stmt = select(Document).where(
            Document.owner_id == current_user.id,
            Document.status == "processed"
        )
        result = await db.execute(stmt)
        docs = result.scalars().all()
        
        if not docs:
            return {
                "success": False,
                "message": "没有找到文档"
            }
        
        results = []
        for doc in docs:
            # 检查文件是否存在
            if not os.path.exists(doc.file_path):
                results.append({
                    "doc_id": doc.doc_id,
                    "filename": doc.filename,
                    "status": "failed",
                    "error": "文件不存在"
                })
                continue
            
            # 加载并索引文档
            texts = rag_llamaindex_service.load_document(doc.file_path, doc.filename)
            collection_name = rag_llamaindex_service.create_vector_store(
                doc_id=doc.doc_id,
                texts=texts,
                filename=doc.filename
            )
            
            results.append({
                "doc_id": doc.doc_id,
                "filename": doc.filename,
                "status": "success",
                "chunks": len(texts),
                "collection_name": collection_name
            })
        
        return {
            "success": True,
            "results": results
        }
        
    except Exception as e:
        import traceback
        return {
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }