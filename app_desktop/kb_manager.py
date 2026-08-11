"""
知识库管理器 - 自动初始化和恢复内置知识库
"""

import os
import shutil
import json
from pathlib import Path
from typing import Optional


class KnowledgeBaseManager:
    """知识库管理器 - 处理内置知识库的初始化和恢复"""
    
    def __init__(self, bundled_kb_path: str = "bundled_kb", 
                 runtime_kb_path: str = "qdrant_data"):
        """
        初始化知识库管理器
        
        Args:
            bundled_kb_path: 内置知识库路径（打包时包含）
            runtime_kb_path: 运行时知识库路径（用户目录）
        """
        # 尝试多个可能的位置
        possible_bundled_paths = [
            Path(bundled_kb_path),
            Path("_internal") / bundled_kb_path,
        ]
        
        # 找到第一个存在的路径
        self.bundled_kb_path = None
        for path in possible_bundled_paths:
            if path.exists():
                self.bundled_kb_path = path
                break
        
        # 如果都不存在，使用第一个作为默认（会在后续报错）
        if self.bundled_kb_path is None:
            self.bundled_kb_path = Path(bundled_kb_path)
        
        self.runtime_kb_path = Path(runtime_kb_path)
        self.metadata_file = self.bundled_kb_path / "metadata.json"
    
    def is_initialized(self) -> bool:
        """
        检查运行时知识库是否已初始化
        
        Returns:
            是否已初始化
        """
        # 检查 qdrant_data 目录是否存在且有内容
        if not self.runtime_kb_path.exists():
            return False
        
        # 检查是否有 collection 目录
        collection_dir = self.runtime_kb_path / "collection"
        if not collection_dir.exists():
            return False
        
        # 检查是否有数据文件
        has_data = any(collection_dir.iterdir())
        return has_data
    
    def get_bundled_metadata(self) -> Optional[dict]:
        """
        获取内置知识库的元数据
        
        Returns:
            元数据字典，如果不存在返回 None
        """
        if not self.metadata_file.exists():
            return None
        
        try:
            with open(self.metadata_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"⚠ 读取元数据失败: {e}")
            return None
    
    def restore_from_bundled(self) -> bool:
        """
        从内置知识库恢复到运行时目录
        
        Returns:
            是否成功
        """
        print("正在初始化知识库...")
        
        # 检查内置知识库是否存在
        if not self.bundled_kb_path.exists():
            print(f"✗ 内置知识库不存在: {self.bundled_kb_path}")
            return False
        
        # 读取元数据
        metadata = self.get_bundled_metadata()
        if metadata:
            print(f"  知识库版本: {metadata.get('version', 'unknown')}")
            print(f"  文档数量: {metadata.get('document_count', 'unknown')}")
            print(f"  最后更新: {metadata.get('last_updated', 'unknown')}")
        
        try:
            # 如果运行时目录已存在，先删除
            if self.runtime_kb_path.exists():
                shutil.rmtree(self.runtime_kb_path)
            
            # 复制内置知识库到运行时目录
            shutil.copytree(
                self.bundled_kb_path / "qdrant_snapshot",
                self.runtime_kb_path
            )
            
            print("✓ 知识库初始化成功")
            return True
            
        except Exception as e:
            print(f"✗ 知识库初始化失败: {e}")
            return False
    
    def ensure_initialized(self) -> bool:
        """
        确保知识库已初始化（如果没有则自动恢复）
        
        Returns:
            是否成功
        """
        if self.is_initialized():
            print("✓ 知识库已就绪")
            return True
        
        print("⚠ 检测到首次运行，正在初始化知识库...")
        return self.restore_from_bundled()
    
    def get_kb_info(self) -> dict:
        """
        获取知识库信息
        
        Returns:
            知识库信息字典
        """
        metadata = self.get_bundled_metadata() or {}
        
        return {
            "initialized": self.is_initialized(),
            "version": metadata.get("version", "unknown"),
            "document_count": metadata.get("document_count", 0),
            "last_updated": metadata.get("last_updated", "unknown"),
            "bundled_path": str(self.bundled_kb_path),
            "runtime_path": str(self.runtime_kb_path)
        }


def create_bundled_kb(source_qdrant_path: str, 
                      output_path: str = "bundled_kb",
                      metadata: Optional[dict] = None):
    """
    创建内置知识库包（在打包前调用）
    
    Args:
        source_qdrant_path: 源 Qdrant 数据路径
        output_path: 输出路径
        metadata: 元数据（版本、文档数等）
    """
    source = Path(source_qdrant_path)
    output = Path(output_path)
    
    print(f"创建内置知识库包...")
    print(f"  源路径: {source}")
    print(f"  目标路径: {output}")
    
    # 创建输出目录
    output.mkdir(exist_ok=True)
    snapshot_dir = output / "qdrant_snapshot"
    
    # 如果已存在，先删除
    if snapshot_dir.exists():
        shutil.rmtree(snapshot_dir)
    
    # 复制 Qdrant 数据（跳过锁文件）
    try:
        def ignore_lock_files(dir, files):
            """忽略锁文件和临时文件"""
            return [f for f in files if f in ['.lock', '.tmp', '~']]
        
        shutil.copytree(source, snapshot_dir, ignore=ignore_lock_files)
        print(f"✓ 数据复制成功")
    except Exception as e:
        print(f"✗ 数据复制失败: {e}")
        return False
    
    # 写入元数据
    if metadata is None:
        metadata = {
            "version": "1.0",
            "document_count": "unknown",
            "last_updated": "unknown"
        }
    
    metadata_file = output / "metadata.json"
    try:
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
        print(f"✓ 元数据写入成功")
    except Exception as e:
        print(f"✗ 元数据写入失败: {e}")
        return False
    
    print(f"✓ 内置知识库包创建完成")
    return True


if __name__ == "__main__":
    import sys
    from datetime import datetime
    
    if len(sys.argv) > 1 and sys.argv[1] == "create":
        # 创建内置知识库包
        source = "../qdrant_data"
        
        # 统计文档数量（简单估算）
        try:
            from qdrant_client import QdrantClient
            client = QdrantClient(path=source)
            collection_info = client.get_collection("personal_kb")
            doc_count = collection_info.points_count
        except:
            doc_count = "unknown"
        
        metadata = {
            "version": "1.0",
            "document_count": doc_count,
            "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "description": "公司知识库快照"
        }
        
        create_bundled_kb(source, "bundled_kb", metadata)
    
    else:
        # 测试初始化
        manager = KnowledgeBaseManager()
        
        print("="*60)
        print("知识库管理器测试")
        print("="*60)
        
        info = manager.get_kb_info()
        print(f"\n当前状态:")
        print(f"  已初始化: {info['initialized']}")
        print(f"  版本: {info['version']}")
        print(f"  文档数: {info['document_count']}")
        print(f"  最后更新: {info['last_updated']}")
        
        if not info['initialized']:
            print(f"\n尝试初始化...")
            success = manager.ensure_initialized()
            print(f"  结果: {'成功' if success else '失败'}")
