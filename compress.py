"""
原始素材压缩模块 - 检测并压缩访谈、聊天等原始素材
"""

import json
from pathlib import Path
from typing import Dict, Tuple

from llm_client import call_llm


def is_raw_material(file_path: str, markdown_content: str) -> bool:
    """
    判断是否是原始素材（聊天记录、访谈、转录等）
    
    这个函数只负责分类，不考虑长度。
    短的聊天记录也应该被标记为 raw_material。
    
    Args:
        file_path: 文件路径
        markdown_content: Markdown 内容
        
    Returns:
        是否为原始素材
    """
    name = Path(file_path).stem.lower()
    
    # 关键词匹配
    raw_keywords = [
        "访谈", "transcript", "interview",
        "聊天", "chat", "对话",
        "recording", "记录"
    ]
    
    # 文件名包含关键词
    if any(kw in name for kw in raw_keywords):
        return True
    
    # .txt 文件（大概率是粘贴的聊天/转录）
    if Path(file_path).suffix.lower() == '.txt':
        return True
    
    return False


def needs_compression(markdown_content: str) -> bool:
    """
    判断内容是否需要压缩
    
    只有足够长的内容才值得压缩。
    
    Args:
        markdown_content: Markdown 内容
        
    Returns:
        是否需要压缩
    """
    return len(markdown_content) >= 5000


def get_source_type(file_path: str) -> str:
    """
    识别原始素材子类型
    
    Args:
        file_path: 文件路径
        
    Returns:
        素材类型: interview / chat / other
    """
    name = Path(file_path).stem.lower()
    
    if any(kw in name for kw in ["访谈", "interview", "transcript"]):
        return "interview"
    
    if any(kw in name for kw in ["聊天", "chat", "对话"]):
        return "chat"
    
    return "other"


def compress_raw_material(
    markdown_content: str,
    source_type: str,
    filename: str
) -> Tuple[str, Dict]:
    """
    压缩原始素材
    
    - 提取核心信息点
    - 保留关键引语和数据
    - 生成结构化摘要
    
    Args:
        markdown_content: Markdown 内容
        source_type: 素材类型 (interview / chat / other)
        filename: 文件名
        
    Returns:
        (压缩后的 Markdown, 额外的 frontmatter 字段)
    """
    # 取前 6000 字符送给 LLM。
    content_sample = markdown_content[:6000]
    original_length = len(markdown_content)
    
    # 根据类型构建不同的 prompt。
    if source_type == "interview":
        system_prompt = """你是研究助手，专门提炼访谈原文的核心内容。
只返回 Markdown 格式内容，不要任何额外说明。
目标：将冗长的访谈转录压缩为结构化的核心信息。"""
        
        user_prompt = f"""以下是访谈转录原文：

{content_sample}

请提炼输出以下结构（Markdown 格式）：

## 受访者核心观点

（3-6 条，每条一句话，提取最重要的观点）

## 关键引语

（最有代表性的 3-5 段原话，保留原文，用引号标注）

## 主要主题

（本次访谈涉及的核心议题，用词组列表表示）

## 潜在研究价值

（这份访谈可能和哪些研究问题相关，1-3 条）"""
    
    elif source_type == "chat":
        system_prompt = """你是研究助手，专门提炼对话记录的核心内容。
只返回 Markdown 格式内容，不要任何额外说明。
目标：从对话中提取关键结论和有价值的分析。"""
        
        user_prompt = f"""以下是对话记录：

{content_sample}

请提炼输出以下结构（Markdown 格式）：

## 关键结论

（本次对话最终达成的结论或决策，3-6 条）

## 有价值的分析观点

（值得保留的分析框架或洞察，2-5 条）

## 遗留问题

（对话中提到但未解决的问题，如有）"""
    
    else:  # other
        system_prompt = """你是研究助手，专门提炼原始文本材料的核心内容。
只返回 Markdown 格式内容，不要任何额外说明。
目标：提取关键信息点和数据。"""
        
        user_prompt = f"""以下是原始文本材料：

{content_sample}

请提炼输出：

## 核心内容摘要

（主要信息点，3-8 条）

## 关键数据或结论

（如有具体数据或明确结论，列出来）"""
    
    # 调用 LLM（自动回退：NVIDIA → Ollama）
    try:
        compressed = call_llm(
            prompt=user_prompt,
            system=system_prompt
        )
        
        if not compressed:
            raise ValueError("LLM 返回空内容")
        
        print(f"  ✓ 压缩成功：{original_length} → {len(compressed)} 字符")
        
    except Exception as e:
        # 失败时截断原文。
        print(f"  ✗ LLM 压缩失败: {e}")
        print(f"  → 使用截断策略")
        
        compressed = markdown_content[:2000] + \
            "\n\n---\n*[自动压缩失败，已截断原文]*"
    
    # 额外的 frontmatter 字段
    extra_frontmatter = {
        "tier": "raw_material",  # 标记为原始素材层级
        "compressed": True,  # 标记已压缩
        "source_length": original_length,  # 原始长度
        "source_type": source_type,  # 素材类型
        "compression_ratio": f"{len(compressed) / original_length:.2%}"  # 压缩比
    }
    
    return compressed, extra_frontmatter


if __name__ == "__main__":
    # 测试代码
    test_content = """
# 合成访谈记录：示例人物关于深度学习的看法

时间：2026-05-25
地点：线上会议

问：您如何看待深度学习的未来发展？

答：我认为深度学习在未来会有更广泛的应用。首先，模型会变得更加高效，
不需要那么多的计算资源。其次，我们会看到更多的跨领域应用，比如在
医疗、金融、教育等领域。第三，可解释性会成为一个重要的研究方向，
因为现在的模型太黑盒了。

问：您觉得最大的挑战是什么？

答：我觉得最大的挑战是数据质量和隐私保护。很多时候我们有大量的数据，
但是质量不高，或者涉及隐私问题不能使用。另外，模型的泛化能力也是
一个挑战，如何让模型在不同的场景下都能表现良好。

问：对于初学者，您有什么建议？

答：我建议初学者先打好基础，理解基本的数学原理，比如线性代数、概率论。
然后多动手实践，从简单的项目开始，逐步深入。不要一开始就追求最新的
技术，而是要理解为什么这些技术有效。
""" * 3  # 重复3次，模拟长文本
    
    # 测试检测
    print("测试 1: 检测原始素材")
    is_raw = is_raw_material("访谈-示例人物.txt", test_content)
    print(f"  is_raw_material: {is_raw}")
    
    if is_raw:
        source_type = get_source_type("访谈-示例人物.txt")
        print(f"  source_type: {source_type}")
        
        # 测试压缩
        print("\n测试 2: 压缩原始素材")
        compressed, extra_meta = compress_raw_material(
            test_content, source_type, "访谈-示例人物.txt"
        )
        
        print(f"\n压缩结果:")
        print(f"  原始长度: {extra_meta['source_length']} 字符")
        print(f"  压缩后长度: {len(compressed)} 字符")
        print(f"  压缩比: {extra_meta['compression_ratio']}")
        print(f"\n压缩内容预览:")
        print(compressed[:500])
