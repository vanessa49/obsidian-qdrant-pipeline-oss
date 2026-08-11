"""
Qdrant 写入模块 - 将文档内容分块并写入 Qdrant 向量数据库
"""

import hashlib
import re
from typing import Dict, List

import requests
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams


class QdrantWriter:
    """Qdrant 向量数据库写入器"""
    
    COLLECTION_NAME = "personal_kb"
    VECTOR_DIM = 1024  # bge-m3 的向量维度
    CHUNK_SIZE = 800  # 每个 chunk 的最大字符数
    
    def __init__(self, qdrant_config: dict,
                 ollama_url: str = "http://localhost:11434"):

        self.ollama_url = ollama_url

        # ===== 核心修改点 =====
        if "path" in qdrant_config:
            self.client = QdrantClient(
                path=qdrant_config["path"]
            )
        else:
            self.client = QdrantClient(
                url=qdrant_config["url"]
            )

        self._ensure_collection()
    
    def _ensure_collection(self):
        """确保 collection 存在，不存在则创建"""
        try:
            collections = self.client.get_collections().collections
            collection_names = [c.name for c in collections]
            
            if self.COLLECTION_NAME not in collection_names:
                print(f"创建 Qdrant collection: {self.COLLECTION_NAME}")
                self.client.create_collection(
                    collection_name=self.COLLECTION_NAME,
                    vectors_config=VectorParams(
                        size=self.VECTOR_DIM,
                        distance=Distance.COSINE
                    )
                )
        except Exception as e:
            print(f"警告: 检查/创建 collection 失败: {e}")
    
    def _split_into_chunks(self, text: str) -> List[str]:
        """
        将文本分块
        
        Args:
            text: 原始文本
            
        Returns:
            文本块列表
        """
        # 按段落分割（以 \n\n 为分隔符）
        paragraphs = re.split(r'\n\n+', text)
        
        chunks = []
        current_chunk = ""
        
        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
            
            # 如果当前 chunk + 新段落不超过限制，直接添加
            if len(current_chunk) + len(para) + 2 <= self.CHUNK_SIZE:
                if current_chunk:
                    current_chunk += "\n\n" + para
                else:
                    current_chunk = para
            else:
                # 保存当前 chunk
                if current_chunk:
                    chunks.append(current_chunk)
                
                # 如果段落本身超过限制，按句子切分
                if len(para) > self.CHUNK_SIZE:
                    sentences = re.split(r'([。！？\n])', para)
                    
                    # 重新组合句子和标点
                    combined_sentences = []
                    for i in range(0, len(sentences) - 1, 2):
                        if i + 1 < len(sentences):
                            combined_sentences.append(sentences[i] + sentences[i + 1])
                        else:
                            combined_sentences.append(sentences[i])
                    
                    # 按句子组合成 chunks
                    current_chunk = ""
                    for sent in combined_sentences:
                        if len(current_chunk) + len(sent) <= self.CHUNK_SIZE:
                            current_chunk += sent
                        else:
                            if current_chunk:
                                chunks.append(current_chunk)
                            current_chunk = sent
                    
                    # 如果还有剩余，作为新的 current_chunk
                    # （不添加到 chunks，因为可能还能和下一个段落合并）
                else:
                    current_chunk = para
        
        # 添加最后一个 chunk
        if current_chunk:
            chunks.append(current_chunk)
        
        return chunks
    
    def _generate_chunk_id(self, file_path: str, chunk_index: int) -> str:
        """
        生成 chunk ID (UUID 格式)
        
        Args:
            file_path: 文件路径
            chunk_index: chunk 索引
            
        Returns:
            UUID 格式的 chunk ID
        """
        import uuid
        content = f"{file_path}_{chunk_index}"
        hash_obj = hashlib.sha256(content.encode('utf-8'))
        # 使用 hash 的前 16 字节生成 UUID
        return str(uuid.UUID(bytes=hash_obj.digest()[:16]))
    
    def _get_embedding(self, text: str) -> List[float]:
        """
        调用 Ollama 获取文本的 embedding
        
        Args:
            text: 文本内容
            
        Returns:
            embedding 向量
        """
        try:
            response = requests.post(
                f"{self.ollama_url}/api/embeddings",
                json={
                    "model": "bge-m3",
                    "prompt": text
                },
                timeout=30
            )
            
            response.raise_for_status()
            result = response.json()
            
            embedding = result.get("embedding")
            if not embedding:
                raise ValueError("API 返回的 embedding 为空")
            
            return embedding
            
        except Exception as e:
            raise RuntimeError(f"获取 embedding 失败: {e}")
    
    def _chunk_exists(self, chunk_id: str) -> bool:
        """
        检查 chunk 是否已存在于 Qdrant
        
        Args:
            chunk_id: chunk ID
            
        Returns:
            是否存在
        """
        try:
            result = self.client.retrieve(
                collection_name=self.COLLECTION_NAME,
                ids=[chunk_id]
            )
            return len(result) > 0
        except Exception:
            return False
    
    def upsert(self, markdown_content: str, frontmatter: Dict, 
               obsidian_path: str, source_file: str) -> tuple[bool, str]:
        """
        将文档内容分块并写入 Qdrant
        
        Args:
            markdown_content: Markdown 内容
            frontmatter: 文档元数据
            obsidian_path: Obsidian vault 中的相对路径
            source_file: 原始文件名
            
        Returns:
            (是否成功, 结果信息)
        """
        try:
            # 分块
            chunks = self._split_into_chunks(markdown_content)
            
            if not chunks:
                return False, "ERROR: 文档内容为空，无法分块"
            
            print(f"  分块: {len(chunks)} 个 chunks")
            
            # 处理每个 chunk
            points = []
            skipped = 0
            
            for idx, chunk in enumerate(chunks):
                chunk_id = self._generate_chunk_id(source_file, idx)
                
                # 检查是否已存在
                if self._chunk_exists(chunk_id):
                    skipped += 1
                    continue
                
                # 获取 embedding
                try:
                    embedding = self._get_embedding(chunk)
                except Exception as e:
                    print(f"  警告: chunk {idx} embedding 失败: {e}")
                    continue
                
                # 创建 point
                point = PointStruct(
                    id=chunk_id,
                    vector=embedding,
                    payload={
                        "source_file": source_file,
                        "obsidian_path": obsidian_path,
                        "chunk_index": idx,
                        "type": frontmatter.get("type", "reference"),
                        "tags": frontmatter.get("tags", []),
                        "date_added": frontmatter.get("date_added", ""),
                        "text": chunk,
                        # 新增字段：支持原始素材标记
                        "tier": frontmatter.get("tier", "processed"),
                        "source_type": frontmatter.get("source_type", ""),
                    }
                )
                
                points.append(point)
            
            # 批量写入 Qdrant
            if points:
                self.client.upsert(
                    collection_name=self.COLLECTION_NAME,
                    points=points
                )
                
                return True, f"写入 {len(points)} 个 chunks (跳过 {skipped} 个已存在)"
            else:
                if skipped > 0:
                    return True, f"SKIP: 所有 {skipped} 个 chunks 已存在"
                else:
                    return False, "ERROR: 没有成功处理任何 chunk"
        
        except Exception as e:
            return False, f"ERROR: {str(e)}"


if __name__ == "__main__":
    import yaml
    from pathlib import Path

    # 优先读 config.yaml，没有就用本地路径兜底
    cfg_path = Path("config.yaml")
    if cfg_path.exists():
        with open(cfg_path, encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
        qdrant_config = cfg.get("qdrant", {"path": "./qdrant_data"})
        ollama_url = cfg.get("ollama", {}).get("url", "http://localhost:11434")
    else:
        qdrant_config = {"path": "./qdrant_data"}
        ollama_url = "http://localhost:11434"

    test_content = """
# 深度学习简介

深度学习是机器学习的一个重要分支，它通过构建多层神经网络来学习数据的表示。

## 主要方法

深度学习包括多种方法：

1. 卷积神经网络（CNN）：主要用于图像处理
2. 循环神经网络（RNN）：主要用于序列数据处理
3. Transformer：目前最流行的架构，用于自然语言处理

## 应用领域

深度学习在以下领域有广泛应用：
- 计算机视觉
- 自然语言处理
- 语音识别
- 推荐系统
"""

    test_frontmatter = {
        "title": "深度学习简介",
        "type": "article",
        "tags": ["deep_learning", "ai"],
        "date_added": "2026-05-25"
    }

    try:
        writer = QdrantWriter(qdrant_config, ollama_url)
        success, result = writer.upsert(
            test_content,
            test_frontmatter,
            "30-articles/2026-05-25-深度学习简介.md",
            "deep_learning.pdf"
        )
        print(f"{'✓' if success else '✗'} {result}")
    except Exception as e:
        print(f"✗ 测试失败: {e}")
