"""
LLM 结构化模块 - 使用 LLM 生成文档 frontmatter
"""

import json
from typing import Dict

from llm_client import call_llm


def structure_document(markdown_content: str, filename: str) -> Dict:
    """
    使用 Ollama 分析文档内容，生成结构化的 frontmatter
    
    Args:
        markdown_content: Markdown 格式的文档内容
        filename: 原始文件名
        
    Returns:
        包含 frontmatter 字段的字典
    """
    # 截取前 4000 字符
    content_sample = markdown_content[:4000] if len(markdown_content) > 4000 else markdown_content
    
    # 构建 prompt
    system_prompt = "你是学术文献整理助手。只返回 JSON，不要任何其他文字。"
    
    user_prompt = f"""请分析以下文档内容，生成结构化的元数据。

文件名: {filename}

内容:
{content_sample}

请返回以下格式的 JSON（不要使用 markdown 代码块）:
{{
  "title": "文档标题",
  "type": "paper|report|article|reference",
  "tags": ["tag1", "tag2"],
  "summary": "一句话摘要，中文，不超过50字",
  "entities": ["实体1", "实体2"]
}}

要求:
- title: 提取文档的主标题，如果没有明确标题则使用文件名
- type: 根据内容判断文档类型（paper=学术论文, report=报告, article=文章, reference=参考资料）
- tags: 3-6个关键词标签，英文小写，用下划线连接多个单词
- summary: 一句话摘要，中文，不超过50字
- entities: 重要的人名、机构名、技术名词等，不超过8个
"""
    
    try:
        # 调用 LLM（自动回退：NVIDIA → Ollama）
        print("  → 调用 LLM 生成结构化数据...")
        generated_text = call_llm(
            prompt=user_prompt,
            system=system_prompt
        )
        
        print("  ✓ LLM 调用成功")
        
        # 尝试解析 JSON
        # 先尝试直接解析
        try:
            frontmatter = json.loads(generated_text)
            print("  ✓ JSON 解析成功（直接解析）")
        except json.JSONDecodeError:
            print("  → JSON 直接解析失败，尝试提取代码块...")
            # 如果失败，尝试提取 JSON 代码块
            if "```json" in generated_text:
                json_start = generated_text.find("```json") + 7
                json_end = generated_text.find("```", json_start)
                json_str = generated_text[json_start:json_end].strip()
                frontmatter = json.loads(json_str)
                print("  ✓ JSON 解析成功（从 ```json 代码块提取）")
            elif "```" in generated_text:
                json_start = generated_text.find("```") + 3
                json_end = generated_text.find("```", json_start)
                json_str = generated_text[json_start:json_end].strip()
                frontmatter = json.loads(json_str)
                print("  ✓ JSON 解析成功（从 ``` 代码块提取）")
            elif "{" in generated_text and "}" in generated_text:
                # 尝试提取第一个 JSON 对象
                json_start = generated_text.find("{")
                json_end = generated_text.rfind("}") + 1
                json_str = generated_text[json_start:json_end]
                frontmatter = json.loads(json_str)
                print("  ✓ JSON 解析成功（提取 JSON 对象）")
            else:
                raise ValueError("无法从响应中提取 JSON")
        
        # 验证必需字段
        required_fields = ["title", "type", "tags", "summary", "entities"]
        for field in required_fields:
            if field not in frontmatter:
                raise ValueError(f"缺少必需字段: {field}")
        
        # 验证 type 字段
        valid_types = ["paper", "report", "article", "reference"]
        if frontmatter["type"] not in valid_types:
            frontmatter["type"] = "reference"
        
        # 验证 tags 和 entities 是列表
        if not isinstance(frontmatter["tags"], list):
            frontmatter["tags"] = []
        if not isinstance(frontmatter["entities"], list):
            frontmatter["entities"] = []
        
        # 限制数量
        frontmatter["tags"] = frontmatter["tags"][:6]
        frontmatter["entities"] = frontmatter["entities"][:8]
        
        print(f"  ✓ 结构化成功: {frontmatter['title']}")
        return frontmatter
        
    except (json.JSONDecodeError, ValueError) as e:
        print(f"  ✗ JSON 解析失败: {e}，使用默认 frontmatter")
        return _create_fallback_frontmatter(filename)
    except RuntimeError as e:
        print(f"  ✗ LLM 调用失败: {e}")
        print(f"    将使用默认 frontmatter")
        return _create_fallback_frontmatter(filename)
    except Exception as e:
        print(f"  ✗ 结构化失败: {e}，使用默认 frontmatter")
        return _create_fallback_frontmatter(filename)


def _create_fallback_frontmatter(filename: str) -> Dict:
    """创建默认的 frontmatter（当 LLM 调用失败时）"""
    from pathlib import Path
    
    # 从文件名提取标题
    title = Path(filename).stem
    
    return {
        "title": title,
        "type": "reference",
        "tags": [],
        "summary": "",
        "entities": []
    }


if __name__ == "__main__":
    # 测试代码
    test_content = """
    # 深度学习在自然语言处理中的应用
    
    本文介绍了深度学习技术在自然语言处理领域的最新进展，
    包括 Transformer 架构、BERT 模型和 GPT 系列模型。
    
    作者：示例作者
    机构：示例机构
    """
    
    result = structure_document(test_content, "deep_learning_nlp.pdf")
    print("\n结果:")
    print(json.dumps(result, ensure_ascii=False, indent=2))
