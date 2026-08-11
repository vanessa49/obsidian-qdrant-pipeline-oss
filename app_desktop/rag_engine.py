"""
RAG 引擎 - 检索增强生成核心逻辑
不修改任何 Qdrant 数据，只读取和查询
"""

import os
import time
from typing import Dict, List, Optional, Tuple

import requests
import yaml
from pathlib import Path
from qdrant_client import QdrantClient


class RAGEngine:
    """RAG 查询引擎"""
    
    def __init__(self, config_path: str = "config_local.yaml"):
        """
        初始化 RAG 引擎
        
        Args:
            config_path: 配置文件路径
        """
        self.config = self._load_config(config_path)
        self.client = self._init_qdrant()
        self.current_model = None  # 记录当前使用的模型
        
    def _load_config(self, config_path: str) -> dict:
        """加载配置文件"""
        # 尝试多个可能的位置
        possible_paths = [
            Path(config_path),
            Path("_internal") / config_path,
        ]
        if config_path == "config_local.yaml":
            possible_paths.extend([
                Path("config.example.yaml"),
                Path("_internal") / "config.example.yaml",
            ])
        
        for path in possible_paths:
            if path.exists():
                with open(path, encoding="utf-8") as f:
                    config = yaml.safe_load(f)
                if not isinstance(config, dict):
                    raise ValueError(f"Configuration must be a mapping: {path}")

                # The process environment is the preferred credential source.
                # This is in-memory only and never writes a local config file.
                environment_api_key = os.environ.get("NVIDIA_API_KEY")
                if environment_api_key:
                    config.setdefault("llm", {}).setdefault("nvidia", {})["api_key"] = environment_api_key
                return config
        
        raise FileNotFoundError(f"配置文件不存在: {config_path}")
    
    def _init_qdrant(self) -> QdrantClient:
        """
        初始化 Qdrant 客户端（优先本地，fallback 远程）
        """
        # 首先确保知识库已初始化
        from kb_manager import KnowledgeBaseManager
        kb_manager = KnowledgeBaseManager()
        
        if not kb_manager.ensure_initialized():
            raise RuntimeError("知识库初始化失败，请检查 bundled_kb 目录")
        
        primary = self.config["qdrant"]["primary"]
        fallback = self.config["qdrant"]["fallback"]
        
        # 尝试主连接（本地模式）
        try:
            if primary["mode"] == "local":
                client = QdrantClient(path=primary["path"])
                # 测试连接
                client.get_collections()
                print(f"✓ Qdrant 连接成功（本地模式）: {primary['path']}")
                return client
        except Exception as e:
            print(f"⚠ 本地 Qdrant 连接失败: {e}")
        
        # Fallback 到远程
        try:
            if fallback["mode"] == "remote":
                client = QdrantClient(url=fallback["url"])
                client.get_collections()
                print(f"✓ Qdrant 连接成功（远程模式）: {fallback['url']}")
                return client
        except Exception as e:
            print(f"✗ 远程 Qdrant 连接失败: {e}")
            raise RuntimeError("无法连接到 Qdrant，请检查配置")
    
    def _get_embedding(self, text: str) -> List[float]:
        """
        获取文本的 embedding（调用内置 Ollama）
        
        Args:
            text: 输入文本
            
        Returns:
            embedding 向量
        """
        embedding_config = self.config["embedding"]["ollama"]
        
        try:
            response = requests.post(
                f"{embedding_config['url']}/api/embeddings",
                json={
                    "model": embedding_config["model"],
                    "prompt": text
                },
                timeout=embedding_config["timeout"]
            )
            
            if response.status_code == 200:
                return response.json()["embedding"]
            else:
                raise RuntimeError(f"Ollama embedding 失败: {response.status_code}")
                
        except Exception as e:
            raise RuntimeError(f"获取 embedding 失败: {e}")
    
    def retrieve(self, question: str) -> List[Dict]:
        """
        从 Qdrant 检索相关文档片段
        
        Args:
            question: 用户问题
            
        Returns:
            检索结果列表，每项包含 text, source, chunk_id, score
        """
        retrieval_config = self.config["retrieval"]
        collection_name = self.config["qdrant"]["collection_name"]
        
        # 获取问题的 embedding
        query_vector = self._get_embedding(question)
        
        # 检索
        results = self.client.query_points(
            collection_name=collection_name,
            query=query_vector,
            limit=retrieval_config["top_k"]
        ).points
        
        # 过滤和格式化结果
        chunks = []
        for r in results:
            if r.score < retrieval_config["score_threshold"]:
                continue
            
            chunks.append({
                "text": r.payload.get("text", ""),
                "source": r.payload.get("obsidian_path", r.payload.get("source_file", "未知来源")),
                "chunk_id": str(r.id),
                "score": r.score,
                "chunk_index": r.payload.get("chunk_index", 0),
                "type": r.payload.get("type", ""),
                "tags": r.payload.get("tags", [])
            })
        
        return chunks
    
    def _truncate_context(self, chunks: List[Dict]) -> Tuple[str, List[Dict]]:
        """
        截断上下文以适应 LLM 限制
        
        Args:
            chunks: 检索到的文档片段
            
        Returns:
            (拼接后的上下文, 使用的 chunks 列表)
        """
        max_length = self.config["retrieval"]["max_context_length"]
        
        context_parts = []
        used_chunks = []
        current_length = 0
        
        for chunk in chunks:
            text = chunk["text"]
            if current_length + len(text) > max_length:
                break
            
            context_parts.append(text)
            used_chunks.append(chunk)
            current_length += len(text)
        
        return "\n\n---\n\n".join(context_parts), used_chunks
    
    def _call_nvidia_api(self, prompt: str, model: str) -> Tuple[bool, str]:
        """
        调用 NVIDIA API
        
        Args:
            prompt: 提示词
            model: 模型名称
            
        Returns:
            (是否成功, 回答内容或错误信息)
        """
        nvidia_config = self.config["llm"]["nvidia"]
        
        try:
            response = requests.post(
                f"{nvidia_config['base_url']}/chat/completions",
                headers={
                    "Authorization": f"Bearer {nvidia_config['api_key']}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": nvidia_config["temperature"],
                    "max_tokens": nvidia_config["max_tokens"]
                },
                timeout=nvidia_config["timeout"]
            )
            
            if response.status_code == 200:
                answer = response.json()["choices"][0]["message"]["content"]
                return True, answer
            else:
                return False, f"API 错误: {response.status_code} - {response.text}"
                
        except Exception as e:
            return False, f"请求失败: {str(e)}"
    
    def generate_answer(self, question: str, chunks: List[Dict]) -> Tuple[str, str]:
        """
        基于检索结果生成回答（多模型回退）
        
        Args:
            question: 用户问题
            chunks: 检索到的文档片段
            
        Returns:
            (回答内容, 使用的模型名称)
        """
        if not chunks:
            return "知识库中没有找到相关内容，无法回答此问题。", "N/A"
        
        # 构建上下文
        context, used_chunks = self._truncate_context(chunks)
        
        # 构建提示词
        prompt = f"""你是一个工业设计与用户研究知识助手。

请优先基于知识库资料回答，但在知识不足时，可以结合你的通用知识提供合理推测、行业经验和灵感启发。

输出规则：

【第一部分：知识库依据】
1. 优先总结参考资料中的相关发现
2. 尽量引用关键研究结论、用户行为、趋势或设计洞察
3. 如果资料有限，请明确说明证据不足

【第二部分：启发性建议（可选）】
当知识库不足以完整回答问题时：
1. 可以基于通用知识、行业经验、设计方法或趋势进行补充
2. 必须明确标记：
   “以下为基于通用知识的推测/灵感，不代表知识库内容”
3. 不要编造“用研研究已经证明”的结论
4. 更偏向提出方向、假设和设计灵感，而不是假装确定答案

回答风格：
- 简洁、结构化
- 更偏洞察与启发，而非学术论文
- 对工业设计、用户体验、消费趋势保持敏感

参考资料：
{context}

问题：{question}

回答："""
        
        # 多模型回退策略
        models = self.config["llm"]["nvidia"]["models"]
        
        for model in models:
            print(f"  尝试模型: {model}")
            success, result = self._call_nvidia_api(prompt, model)
            
            if success:
                self.current_model = model
                return result, model
            else:
                print(f"  ✗ {model} 失败: {result}")
                time.sleep(1)  # 避免频繁重试
        
        # 所有模型都失败
        return "抱歉，所有 LLM 模型都无法响应，请稍后重试。", "失败"
    
    def ask(self, question: str) -> Dict:
        """
        完整的 RAG 查询流程
        
        Args:
            question: 用户问题
            
        Returns:
            结果字典，包含 answer, sources, model, retrieval_count
        """
        # Step 1: 检索
        print(f"🔍 检索相关内容...")
        chunks = self.retrieve(question)
        print(f"  找到 {len(chunks)} 条相关内容")
        
        if not chunks:
            return {
                "answer": "知识库中没有找到相关内容。",
                "sources": [],
                "model": "N/A",
                "retrieval_count": 0
            }
        
        # Step 2: 生成回答
        print(f"💬 生成回答...")
        answer, model = self.generate_answer(question, chunks)
        
        # Step 3: 整理来源
        sources = []
        seen_sources = set()
        
        for chunk in chunks[:5]:  # 只显示前 5 个来源
            source_key = f"{chunk['source']}#{chunk['chunk_index']}"
            if source_key not in seen_sources:
                sources.append({
                    "file": chunk["source"],
                    "chunk_index": chunk["chunk_index"],
                    "score": round(chunk["score"], 3),
                    "preview": chunk["text"][:100] + "..." if len(chunk["text"]) > 100 else chunk["text"]
                })
                seen_sources.add(source_key)
        
        return {
            "answer": answer,
            "sources": sources,
            "model": model,
            "retrieval_count": len(chunks)
        }


if __name__ == "__main__":
    # 测试
    import sys
    
    engine = RAGEngine()
    
    question = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "深度学习是什么？"
    
    print(f"\n问题: {question}\n")
    result = engine.ask(question)
    
    print("\n" + "="*60)
    print("回答:")
    print("="*60)
    print(result["answer"])
    
    print("\n" + "="*60)
    print(f"来源 (共 {result['retrieval_count']} 条检索结果):")
    print("="*60)
    for i, src in enumerate(result["sources"], 1):
        print(f"{i}. {src['file']} #chunk_{src['chunk_index']} (相似度: {src['score']})")
        print(f"   预览: {src['preview']}\n")
    
    print(f"使用模型: {result['model']}")
