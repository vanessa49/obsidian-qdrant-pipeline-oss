"""
Obsidian 写入模块 - 将 Markdown 内容写入 Obsidian vault
"""

import re
from datetime import datetime
from pathlib import Path
from typing import Dict

import yaml


class ObsidianWriter:
    """Obsidian vault 写入器"""
    
    # 类型到文件夹的映射
    TYPE_FOLDER_MAP = {
        "paper": "10-papers",
        "report": "20-my-reports",
        "article": "30-articles",
        "reference": "40-reference",
        "interview": "50-interviews"
    }
    
    DEFAULT_FOLDER = "00-inbox"
    
    def __init__(self, vault_path: str):
        """
        初始化 Obsidian 写入器
        
        Args:
            vault_path: Obsidian vault 的根路径
        """
        self.vault_path = Path(vault_path)
        
        if not self.vault_path.exists():
            raise ValueError(f"Vault 路径不存在: {vault_path}")
        
        # 确保所有目标文件夹存在
        self._ensure_folders()
    
    def _ensure_folders(self):
        """确保所有目标文件夹存在"""
        folders = list(self.TYPE_FOLDER_MAP.values()) + [self.DEFAULT_FOLDER]
        
        for folder in folders:
            folder_path = self.vault_path / folder
            folder_path.mkdir(parents=True, exist_ok=True)
    
    def _sanitize_filename(self, title: str) -> str:
        """
        清理文件名，移除特殊字符
        
        Args:
            title: 原始标题
            
        Returns:
            清理后的文件名（不含扩展名）
        """
        # 替换空格为连字符
        filename = title.replace(" ", "-")
        
        # 移除特殊字符，只保留字母、数字、连字符、下划线和中文字符
        filename = re.sub(r'[^\w\u4e00-\u9fff\-]', '', filename)
        
        # 限制长度为 40 个字符
        if len(filename) > 40:
            filename = filename[:40]
        
        # 移除首尾的连字符
        filename = filename.strip('-')
        
        return filename
    
    def _get_target_folder(self, doc_type: str) -> Path:
        """
        根据文档类型获取目标文件夹
        
        Args:
            doc_type: 文档类型
            
        Returns:
            目标文件夹路径
        """
        folder_name = self.TYPE_FOLDER_MAP.get(doc_type, self.DEFAULT_FOLDER)
        return self.vault_path / folder_name
    
    def _generate_filename(self, frontmatter: Dict) -> str:
        """
        生成文件名
        
        Args:
            frontmatter: 文档元数据
            
        Returns:
            文件名（含 .md 扩展名）
        """
        # 获取今天日期
        today = datetime.now().strftime("%Y-%m-%d")
        
        # 清理标题
        title = frontmatter.get("title", "untitled")
        clean_title = self._sanitize_filename(title)
        
        # 组合文件名
        filename = f"{today}-{clean_title}.md"
        
        return filename
    
    def _create_frontmatter_yaml(self, frontmatter: Dict, source_file: str) -> str:
        """
        创建 YAML frontmatter
        
        Args:
            frontmatter: 文档元数据
            source_file: 原始文件名
            
        Returns:
            YAML 格式的 frontmatter 字符串
        """
        # 添加额外字段
        frontmatter_with_meta = {
            **frontmatter,
            "source_file": source_file,
            "date_added": datetime.now().strftime("%Y-%m-%d")
        }
        
        # 转换为 YAML
        yaml_str = yaml.dump(
            frontmatter_with_meta,
            allow_unicode=True,
            default_flow_style=False,
            sort_keys=False
        )
        
        return f"---\n{yaml_str}---\n\n"
    
    def write(self, markdown_content: str, frontmatter: Dict, source_file: str) -> tuple[bool, str]:
        """
        写入文档到 Obsidian vault
        
        Args:
            markdown_content: Markdown 内容
            frontmatter: 文档元数据
            source_file: 原始文件名
            
        Returns:
            (是否成功, 目标文件路径或错误信息)
        """
        try:
            # 获取目标文件夹
            doc_type = frontmatter.get("type", "reference")
            target_folder = self._get_target_folder(doc_type)
            
            # 生成文件名
            filename = self._generate_filename(frontmatter)
            target_path = target_folder / filename
            
            # 检查文件是否已存在
            if target_path.exists():
                return False, f"SKIP: 文件已存在 - {target_path.relative_to(self.vault_path)}"
            
            # 创建完整内容
            frontmatter_yaml = self._create_frontmatter_yaml(frontmatter, source_file)
            full_content = frontmatter_yaml + markdown_content
            
            # 写入文件
            target_path.write_text(full_content, encoding='utf-8')
            
            relative_path = target_path.relative_to(self.vault_path)
            return True, str(relative_path)
            
        except Exception as e:
            return False, f"ERROR: {str(e)}"


if __name__ == "__main__":
    # 测试代码
    import tempfile
    
    # 创建临时 vault
    with tempfile.TemporaryDirectory() as tmpdir:
        writer = ObsidianWriter(tmpdir)
        
        # 测试写入
        test_frontmatter = {
            "title": "测试文档：深度学习",
            "type": "paper",
            "tags": ["deep_learning", "ai"],
            "summary": "这是一篇关于深度学习的论文",
            "entities": ["Example Person", "Example Organization"]
        }
        
        test_content = """
# 深度学习简介

深度学习是机器学习的一个分支...

## 主要方法

1. 卷积神经网络
2. 循环神经网络
3. Transformer
"""
        
        success, result = writer.write(test_content, test_frontmatter, "test.pdf")
        
        if success:
            print(f"✓ 写入成功: {result}")
            
            # 读取并显示内容
            full_path = Path(tmpdir) / result
            print("\n文件内容:")
            print(full_path.read_text(encoding='utf-8')[:500])
        else:
            print(f"✗ 写入失败: {result}")
