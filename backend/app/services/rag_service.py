# app/services/rag_service.py
import os
from typing import List, Optional, Dict, Any
from rank_bm25 import BM25Okapi
import jieba
from langchain_community.vectorstores import Chroma
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import TextLoader, PyPDFLoader
from app.core.config import settings
import asyncio
import numpy as np

VECTOR_STORE_DIR = "./chroma_db"

class RAGService:
    def __init__(self):
        self.embeddings = OpenAIEmbeddings(
            model="BAAI/bge-m3",
            openai_api_key=settings.rag_api_key,
            openai_api_base="https://api.siliconflow.cn/v1"
        )
        
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=500,
            chunk_overlap=50,
            separators=["\n\n", "\n", "。", "！", "？", "；", "，", " ", ""]
        )
        
        os.makedirs(VECTOR_STORE_DIR, exist_ok=True)
        os.makedirs("./uploads", exist_ok=True)

    def load_document(self, file_path: str, filename: str) -> List[str]:
        """加载文档并切分"""
        if filename.endswith('.pdf'):
            loader = PyPDFLoader(file_path)
        else:
            loader = TextLoader(file_path, encoding='utf-8')
        
        documents = loader.load()
        chunks = self.text_splitter.split_documents(documents)
        return [chunk.page_content for chunk in chunks]

    def create_vector_store(self, doc_id: str, texts: List[str], filename: str) -> str:
        """创建向量存储"""
        print(f"📤 正在创建 Chroma 向量存储，文本数量: {len(texts)}")
        
        collection_name = f"doc_{doc_id}"
        
        metadatas = [
            {
                "doc_id": doc_id,
                "filename": filename,
                "chunk_index": i,
                "total_chunks": len(texts)
            }
            for i in range(len(texts))
        ]
        
        vector_store = Chroma.from_texts(
            texts=texts,
            embedding=self.embeddings,
            collection_name=collection_name,
            persist_directory=VECTOR_STORE_DIR,
            metadatas=metadatas
        )
        
        print(f"✅ Chroma 向量存储已保存到: {VECTOR_STORE_DIR}")
        return collection_name

    def _bm25_search(self, texts: List[str], query: str, top_k: int = 3) -> List[tuple]:
        """使用 BM25 进行关键词检索"""
        tokenized_corpus = [list(jieba.cut(text)) for text in texts]
        bm25 = BM25Okapi(tokenized_corpus)
        tokenized_query = list(jieba.cut(query))
        scores = bm25.get_scores(tokenized_query)
        
        results = sorted(
            [(texts[i], scores[i]) for i in range(len(texts))],
            key=lambda x: x[1],
            reverse=True
        )
        return results[:top_k]

    async def hybrid_search(
        self,
        doc_id: str,
        query: str,
        top_k: int = 5,
        vector_weight: float = 0.7,
        bm25_weight: float = 0.3,
        filename_filter: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """混合检索：向量检索 + BM25 关键词检索"""
        collection_name = f"doc_{doc_id}"
        
        vector_store = Chroma(
            collection_name=collection_name,
            embedding_function=self.embeddings,
            persist_directory=VECTOR_STORE_DIR
        )
        
        all_docs = vector_store.get()
        all_texts = all_docs.get("documents", [])
        
        if not all_texts:
            return []
        
        vector_results = vector_store.similarity_search_with_score(query, k=top_k * 2)
        vector_scores = {doc.page_content: score for doc, score in vector_results}
        
        bm25_results = self._bm25_search(all_texts, query, top_k=top_k * 2)
        bm25_scores = {text: score for text, score in bm25_results}
        
        all_contents = set(vector_scores.keys()) | set(bm25_scores.keys())
        combined = []
        
        for content in all_contents:
            v_score = vector_scores.get(content, 0)
            b_score = bm25_scores.get(content, 0)
            v_norm = min(v_score / 2, 1.0)
            b_norm = min(b_score / 10, 1.0)
            
            combined_score = vector_weight * v_norm + bm25_weight * b_norm
            
            metadata = {}
            for doc in vector_store.get()["metadatas"]:
                if doc.get("content") == content:
                    metadata = doc
                    break
            
            combined.append({
                "content": content,
                "score": combined_score,
                "doc_id": doc_id,
                "filename": metadata.get("filename", "未知")
            })
        
        combined.sort(key=lambda x: x["score"], reverse=True)
        return combined[:top_k]

    async def get_document_summary(self, doc_id: str) -> str:
        """获取文档摘要（前 200 个字符）"""
        collection_name = f"doc_{doc_id}"
        vector_store = Chroma(
            collection_name=collection_name,
            embedding_function=self.embeddings,
            persist_directory=VECTOR_STORE_DIR
        )
        all_docs = vector_store.get()
        if all_docs.get("documents"):
            return all_docs["documents"][0][:200]
        return ""

    async def _get_embedding(self, text: str) -> List[float]:
        """获取文本的向量"""
        return await asyncio.to_thread(self.embeddings.embed_query, text)

    def _cosine_similarity(self, a: List[float], b: List[float]) -> float:
        """计算余弦相似度"""
        return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

    async def route_documents(self, doc_ids: List[str], query: str) -> List[str]:
        """使用大模型判断哪些文档与用户问题相关，如果没有相关文档则返回空列表"""
        
        # 1. 获取所有文档的摘要
        doc_summaries = {}
        for doc_id in doc_ids:
            collection_name = f"doc_{doc_id}"
            try:
                vector_store = Chroma(
                    collection_name=collection_name,
                    embedding_function=self.embeddings,
                    persist_directory=VECTOR_STORE_DIR
                )
                all_docs = vector_store.get()
                if all_docs.get("documents"):
                    summary = all_docs["documents"][0][:200]
                    filename = "未知"
                    if all_docs.get("metadatas"):
                        filename = all_docs["metadatas"][0].get("filename", "未知")
                    doc_summaries[doc_id] = {"filename": filename, "summary": summary}
            except Exception as e:
                print(f"⚠️ 获取文档 {doc_id} 信息失败: {e}")
                doc_summaries[doc_id] = {"filename": "未知", "summary": ""}
        
        # 2. 构建 prompt，让大模型判断是否相关并选择文档
        docs_text = ""
        for doc_id, info in doc_summaries.items():
            docs_text += f"文档 {doc_id}: {info['filename']}\n内容摘要：{info['summary'][:100]}...\n\n"
        
        prompt = f"""请根据用户问题，判断下面哪些文档可能与问题相关。

    {docs_text}

    用户问题：{query}

    判断规则：
    1. 如果用户问题与所有文档的内容都无关，只返回 "无"
    2. 如果用户问题与某个文档相关，返回该文档的 ID
    3. 如果多个文档相关，返回最多 2 个文档 ID，用逗号分隔
    4. 只返回文档 ID 或 "无"，不要有其他内容

    示例：
    - 用户问"赵霞是谁"，文档中有赵霞的信息 → 返回文档 ID
    - 用户问"今天天气怎么样"，所有文档都没有相关内容 → 返回"无"
    """
        
        from app.services.agent_service import agent_service
        response = await agent_service.chat([{"role": "user", "content": prompt}])
        print(f"📊 [路由] 大模型返回: {response}")
        
        # 3. 解析返回结果
        response = response.strip()
        if "无" in response:
            print(f"📊 [路由] 判断为不相关，返回空列表")
            return []
        
        selected_ids = []
        for part in response.replace("，", ",").split(","):
            part = part.strip()
            part = part.replace("'", "").replace('"', "").strip()
            if part in doc_ids:
                selected_ids.append(part)
        
        print(f"📊 [路由] 选中的文档: {selected_ids}")
        return selected_ids[:2]

    async def search_all_documents(
        self,
        doc_ids: List[str],
        query: str,
        top_k_per_doc: int = 3,
        final_top_k: int = 3
    ) -> List[Dict[str, Any]]:
        """使用大模型路由 + 混合检索"""
        doc_filenames = {}
        for doc_id in doc_ids:
            collection_name = f"doc_{doc_id}"
            try:
                vector_store = Chroma(
                    collection_name=collection_name,
                    embedding_function=self.embeddings,
                    persist_directory=VECTOR_STORE_DIR
                )
                all_docs = vector_store.get()
                if all_docs.get("metadatas"):
                    filename = all_docs["metadatas"][0].get("filename", "")
                    doc_filenames[doc_id] = filename
            except Exception as e:
                print(f"⚠️ 获取文档 {doc_id} 信息失败: {e}")
                doc_filenames[doc_id] = "未知"
        
        target_docs = await self.route_documents(doc_ids, query)
        print(f"📊 路由选中的文档: {target_docs}")
        
        all_results = []
        for doc_id in target_docs:
            results = await self.hybrid_search(
                doc_id=doc_id,
                query=query,
                top_k=top_k_per_doc,
                vector_weight=0.7,
                bm25_weight=0.3
            )
            filename = doc_filenames.get(doc_id, "未知")
            for r in results:
                r["doc_id"] = doc_id
                r["filename"] = filename
                all_results.append(r)
        
        all_results.sort(key=lambda x: x["score"], reverse=True)
        final_results = all_results[:final_top_k]
        
        print(f"📊 最终结果:")
        for i, r in enumerate(final_results):
            print(f"  {i+1}. [{r['filename']}] 分数: {r['score']:.4f} - {r['content'][:30]}...")
        
        return final_results

rag_service = RAGService()