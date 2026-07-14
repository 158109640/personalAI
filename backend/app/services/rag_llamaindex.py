# backend/app/services/rag_llamaindex.py
import os
import json
import httpx
import re
from typing import List, Dict, Any, Optional
from pathlib import Path
from pydantic import Field

from llama_index.core import (
    SimpleDirectoryReader,
    VectorStoreIndex,
    Settings,
    StorageContext,
    Document as LlamaDocument,
)
from llama_index.core.node_parser import SentenceWindowNodeParser
from llama_index.core.postprocessor import MetadataReplacementPostProcessor
from llama_index.core.embeddings import BaseEmbedding
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.llms.openai import OpenAI

import chromadb
from app.core.config import settings

# ===== 配置目录 =====
VECTOR_STORE_DIR = "./chroma_db_llamaindex"
DOC_SUMMARIES_DIR = "./doc_summaries_llamaindex"
os.makedirs(VECTOR_STORE_DIR, exist_ok=True)
os.makedirs(DOC_SUMMARIES_DIR, exist_ok=True)


# ============================================================
# 自定义嵌入模型（硅基流动适配器）
# ============================================================
class SiliconFlowEmbedding(BaseEmbedding):
    """硅基流动嵌入模型适配器 - 完全同步版本"""

    api_key: str = Field(description="API Key")
    api_base: str = Field(default="https://api.siliconflow.cn/v1", description="API Base URL")
    model: str = Field(default="BAAI/bge-m3", description="模型名称")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    @classmethod
    def class_name(cls) -> str:
        return "SiliconFlowEmbedding"

    # ===== 同步方法（核心实现） =====
    def _get_query_embedding(self, query: str) -> List[float]:
        """同步获取查询向量"""
        return self._get_embedding_sync(query)

    def _get_text_embedding(self, text: str) -> List[float]:
        """同步获取文本向量"""
        return self._get_embedding_sync(text)

    def _get_embedding_sync(self, text: str) -> List[float]:
        """同步调用硅基流动 API 获取向量"""
        url = f"{self.api_base}/embeddings"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": self.model,
            "input": text
        }

        with httpx.Client(timeout=60.0) as client:
            response = client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
            return data["data"][0]["embedding"]

    # ===== 异步方法（调用同步方法） =====
    async def _aget_query_embedding(self, query: str) -> List[float]:
        """异步获取查询向量"""
        # 在线程池中运行同步方法
        import asyncio
        return await asyncio.to_thread(self._get_query_embedding, query)

    async def _aget_text_embedding(self, text: str) -> List[float]:
        """异步获取文本向量"""
        import asyncio
        return await asyncio.to_thread(self._get_text_embedding, text)

    async def _aget_text_embedding_batch(self, texts: List[str], **kwargs) -> List[List[float]]:
        """异步批量获取文本向量"""
        import asyncio
        results = []
        for text in texts:
            embedding = await asyncio.to_thread(self._get_text_embedding, text)
            results.append(embedding)
        return results


# ============================================================
# LlamaIndex RAG 服务
# ============================================================
class LlamaIndexRAGService:
    def __init__(self):
        # ===== 使用自定义嵌入模型 =====
        self.embed_model = SiliconFlowEmbedding(
            api_key=settings.rag_api_key,
            api_base="https://api.siliconflow.cn/v1",
            model="BAAI/bge-m3"
        )
        Settings.embed_model = self.embed_model

        # ===== LLM =====
        Settings.llm = OpenAI(
            model=settings.deepseek_model,
            api_key=settings.deepseek_api_key,
            api_base=settings.deepseek_base_url
        )

        # ===== 配置节点解析器（Sentence Window） =====
        # 这是解决"李朝辉是谁"问题的关键！
        self.node_parser = SentenceWindowNodeParser.from_defaults(
            window_size=1,  # 检索时返回前后各3个句子
            window_metadata_key="window",
            original_text_metadata_key="original_text",
        )

        # ===== 初始化 ChromaDB 客户端 =====
        self.chroma_client = chromadb.PersistentClient(path=VECTOR_STORE_DIR)

        print("✅ LlamaIndex RAG 服务初始化完成")

    def _get_collection_name(self, doc_id: str) -> str:
        """获取集合名称"""
        if doc_id.startswith("doc_"):
            return doc_id
        return f"doc_{doc_id}"

    def _get_summary_path(self, doc_id: str) -> str:
        """获取摘要文件路径"""
        return os.path.join(DOC_SUMMARIES_DIR, f"{doc_id}.json")

    def load_document(self, file_path: str, filename: str) -> List[str]:
        """加载文档并提取文本内容"""
        try:
            if filename.lower().endswith('.pdf'):
                # ===== 使用 PyPDFLoader 读取 PDF =====
                from langchain_community.document_loaders import PyPDFLoader
                loader = PyPDFLoader(file_path)
                pages = loader.load()
                full_text = "\n".join([page.page_content for page in pages])
                print(f"✅ PDF 加载成功，共 {len(pages)} 页")
                print(f"📊 文档预览: {full_text[:200]}...")
                return [full_text]
            else:
                # 文本文件直接读取
                with open(file_path, 'r', encoding='utf-8') as f:
                    full_text = f.read()
                print(f"✅ 文本文件加载成功，长度: {len(full_text)}")
                return [full_text]
        except Exception as e:
            print(f"❌ 加载文档失败: {e}")
            import traceback
            traceback.print_exc()
            return []

    def create_vector_store(self, doc_id: str, texts: List[str], filename: str) -> str:
        """创建向量存储（带句子窗口）"""
        print(f"📤 正在创建 LlamaIndex 向量存储，文本数量: {len(texts)}")

        collection_name = self._get_collection_name(doc_id)

        # 1. 获取或创建 Chroma 集合
        try:
            self.chroma_client.delete_collection(collection_name)
        except:
            pass
        chroma_collection = self.chroma_client.create_collection(collection_name)

        # 2. 创建向量存储
        vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
        storage_context = StorageContext.from_defaults(vector_store=vector_store)

        # 3. 构建 LlamaIndex 文档
        full_text = "\n".join(texts)
        llama_doc = LlamaDocument(
            text=full_text,
            metadata={
                "doc_id": doc_id,
                "filename": filename,
            }
        )

        # 4. 使用 SentenceWindow 解析器处理文档
        nodes = self.node_parser.get_nodes_from_documents([llama_doc])
        print(f"📊 生成了 {len(nodes)} 个句子节点")

        # 5. 创建索引
        index = VectorStoreIndex(
            nodes=nodes,
            storage_context=storage_context,
            embed_model=Settings.embed_model,
        )

        # 6. 保存索引到磁盘
        persist_dir = f"{VECTOR_STORE_DIR}/{collection_name}"
        index.storage_context.persist(persist_dir=persist_dir)

        # 7. 保存文档摘要
        summary = full_text[:500]
        with open(self._get_summary_path(doc_id), "w", encoding="utf-8") as f:
            json.dump({
                "doc_id": doc_id,
                "filename": filename,
                "summary": summary,
                "full_text_length": len(full_text)
            }, f, ensure_ascii=False, indent=2)

        print(f"✅ 向量存储创建成功: {collection_name}")
        return collection_name

    def get_document_summary(self, doc_id: str) -> str:
        """获取文档摘要"""
        summary_path = self._get_summary_path(doc_id)
        try:
            with open(summary_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("summary", "")
        except:
            return ""

    def get_document_filename(self, doc_id: str) -> str:
        """获取文档文件名"""
        summary_path = self._get_summary_path(doc_id)
        try:
            with open(summary_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("filename", "未知")
        except:
            return "未知"

    async def search_all_documents(
        self,
        doc_ids: List[str],
        query: str,
        top_k: int = 5,
        similarity_cutoff: float = 0.2
    ) -> List[Dict[str, Any]]:
        """在所有文档中检索相关片段 - 直接搜索所有集合"""
        print(f"📊 查询: {query}")
        print(f"📊 传入的 doc_ids: {doc_ids}，但将忽略它们，搜索所有集合")

        all_results = []

        # 获取查询向量
        try:
            query_embedding = self.embed_model._get_query_embedding(query)
            print(f"✅ 查询向量获取成功，维度: {len(query_embedding)}")
        except Exception as e:
            print(f"❌ 获取查询向量失败: {e}")
            return []

        # ===== 获取所有集合 =====
        all_collections = self.chroma_client.list_collections()
        collection_names = [col.name for col in all_collections]
        print(f"📊 所有集合: {collection_names}")

        if not collection_names:
            print("⚠️ 没有找到任何集合")
            return []

        for collection_name in collection_names:
            try:
                chroma_collection = self.chroma_client.get_collection(collection_name)
                print(f"✅ 搜索集合: {collection_name}，文档数: {chroma_collection.count()}")

                # 如果集合为空，跳过
                if chroma_collection.count() == 0:
                    print(f"⚠️ 集合 {collection_name} 为空，跳过")
                    continue

                results = chroma_collection.query(
                    query_embeddings=[query_embedding],
                    n_results=top_k,
                    include=["documents", "metadatas", "distances"]
                )

                print(f"🔍 集合 {collection_name} 查询结果: {results}")

                if results and results['documents'] and results['documents'][0]:
                    # 从 metadata 中获取文件名
                    metadatas = results.get('metadatas', [[]])[0]
                    for i, doc_text in enumerate(results['documents'][0]):
                        distance = results['distances'][0][i] if results['distances'] else 0.5
                        score = max(0, 1.0 - distance)

                        if score >= similarity_cutoff:
                            # 从 metadata 获取文件名
                            filename = "未知"
                            if i < len(metadatas) and metadatas[i]:
                                filename = metadatas[i].get("filename", "未知")
                            
                            all_results.append({
                                "content": doc_text,
                                "score": score,
                                "doc_id": collection_name.replace("doc_", ""),
                                "filename": filename,
                            })
                            print(f"  ✅ 片段 {i+1}: 分数={score:.3f}")

            except Exception as e:
                print(f"⚠️ 搜索集合 {collection_name} 失败: {e}")
                import traceback
                traceback.print_exc()
                continue

        # 去重并排序
        seen_contents = set()
        unique_results = []
        for r in sorted(all_results, key=lambda x: x["score"], reverse=True):
            content_key = r["content"][:100]
            if content_key not in seen_contents:
                seen_contents.add(content_key)
                unique_results.append(r)

        print(f"📊 最终返回 {len(unique_results)} 个唯一片段")
        return unique_results[:top_k]  # 返回前 top_k 个结果
    

    async def search_single_document(
        self,
        doc_id: str,
        query: str,
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """在单个文档中检索"""
        return await self.search_all_documents(
            doc_ids=[doc_id],
            query=query,
            top_k=top_k
        )

    async def route_documents(
        self,
        doc_ids: List[str],
        query: str
    ) -> List[str]:
        """使用摘要快速判断哪些文档相关（关键词匹配）"""
        print(f"📊 路由文档，检查 {len(doc_ids)} 个文档")

        # 从查询中提取关键词
        keywords = []
        chinese_words = re.findall(r'[\u4e00-\u9fa5]{2,4}', query)
        keywords.extend(chinese_words)
        english_words = re.findall(r'[a-zA-Z]{2,}', query)
        keywords.extend([w.lower() for w in english_words])

        print(f"📊 提取的关键词: {keywords}")

        relevant_docs = []
        for doc_id in doc_ids:
            summary = self.get_document_summary(doc_id)
            filename = self.get_document_filename(doc_id)
            if not summary:
                continue

            match_score = 0
            for kw in keywords:
                if kw in summary or kw in filename:
                    match_score += 1

            if match_score > 0:
                relevant_docs.append(doc_id)
                print(f"✅ 文档 {doc_id} ({filename}) 匹配，分数: {match_score}")

        if not relevant_docs:
            print(f"📊 没有文档匹配，返回所有文档")
            return doc_ids[:2]

        return relevant_docs[:2]


# ===== 单例 =====
rag_llamaindex_service = LlamaIndexRAGService()