"""
批量处理图片文件夹 - 将图片内容提取为文本并导入知识库
适用场景：聊天记录截图、图表、扫描件等
"""

import sys
from pathlib import Path
from typing import List
import yaml

from convert import _image_to_base64, _call_vision_api_with_fallback, ConversionError
from PIL import Image
from qdrant_writer import QdrantWriter


def load_config(config_path: str = "config.yaml") -> dict:
    """加载配置文件"""
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def process_image(image_path: Path, prompt: str = None) -> str:
    """
    处理单张图片，提取内容
    
    Args:
        image_path: 图片路径
        prompt: 自定义提示词（可选）
    
    Returns:
        提取的文本内容
    """
    if prompt is None:
        prompt = """这是一张图片，可能是聊天记录截图、图表或文档。

请提取所有有用信息：
1) 如果是聊天记录：提取对话内容、时间、参与者
2) 如果是图表：提取数据、趋势、结论
3) 如果是文档/PPT截图：提取标题、正文、要点
4) 如果是其他内容：提取所有可见文字和关键信息

用简洁的中文输出，保持原有结构。不要描述颜色、布局等视觉元素。"""
    
    try:
        print(f"  处理: {image_path.name}")
        
        # 读取图片
        image = Image.open(image_path)
        
        # 转换为 base64
        base64_image = _image_to_base64(image)
        
        # 调用 Vision API
        result = _call_vision_api_with_fallback(base64_image, prompt)
        
        # 检查是否提取失败
        if result.startswith("[图片页，提取失败"):
            print(f"    ⚠️  提取失败: {result}")
            return None
        
        print(f"    ✓ 提取成功 ({len(result)} 字符)")
        return result
        
    except Exception as e:
        print(f"    ✗ 错误: {str(e)}")
        return None


def process_image_folder(
    folder_path: str,
    output_format: str = "combined",
    custom_prompt: str = None
) -> List[dict]:
    """
    批量处理图片文件夹
    
    Args:
        folder_path: 图片文件夹路径
        output_format: 输出格式
            - "combined": 合并为一个文档
            - "individual": 每张图片单独一个文档
        custom_prompt: 自定义提示词
    
    Returns:
        文档列表 [{"content": "...", "metadata": {...}}, ...]
    """
    folder = Path(folder_path)
    
    if not folder.exists():
        raise ValueError(f"文件夹不存在: {folder_path}")
    
    # 支持的图片格式
    image_extensions = {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp'}
    
    # 查找所有图片
    image_files = [
        f for f in folder.iterdir()
        if f.is_file() and f.suffix.lower() in image_extensions
    ]
    
    if not image_files:
        print(f"⚠️  文件夹中没有找到图片: {folder_path}")
        return []
    
    # 按文件名排序
    image_files.sort()
    
    print(f"\n找到 {len(image_files)} 张图片")
    print("="*50)
    
    # 处理每张图片
    results = []
    
    for idx, image_file in enumerate(image_files, start=1):
        print(f"\n[{idx}/{len(image_files)}]")
        
        content = process_image(image_file, custom_prompt)
        
        if content:
            results.append({
                "filename": image_file.name,
                "content": content,
                "path": str(image_file)
            })
    
    print("\n" + "="*50)
    print(f"✓ 成功处理 {len(results)}/{len(image_files)} 张图片")
    
    # 根据输出格式组织文档
    if output_format == "combined":
        # 合并为一个文档
        combined_content = f"# {folder.name} - 图片内容提取\n\n"
        combined_content += f"来源文件夹: {folder_path}\n"
        combined_content += f"图片数量: {len(results)}\n\n"
        combined_content += "---\n\n"
        
        for idx, result in enumerate(results, start=1):
            combined_content += f"## 图片 {idx}: {result['filename']}\n\n"
            combined_content += result['content']
            combined_content += "\n\n---\n\n"
        
        return [{
            "content": combined_content,
            "metadata": {
                "source": folder_path,
                "type": "image_batch",
                "image_count": len(results)
            }
        }]
    
    else:  # individual
        # 每张图片单独一个文档
        documents = []
        for result in results:
            doc_content = f"# {result['filename']}\n\n"
            doc_content += f"来源: {result['path']}\n\n"
            doc_content += "---\n\n"
            doc_content += result['content']
            
            documents.append({
                "content": doc_content,
                "metadata": {
                    "source": result['path'],
                    "type": "image",
                    "filename": result['filename']
                }
            })
        
        return documents


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="批量处理图片文件夹，提取内容并导入知识库"
    )
    parser.add_argument(
        "folder",
        help="图片文件夹路径（如: kb-inbox）"
    )
    parser.add_argument(
        "--format",
        choices=["combined", "individual"],
        default="combined",
        help="输出格式：combined=合并为一个文档，individual=每张图片单独文档"
    )
    parser.add_argument(
        "--prompt",
        help="自定义提示词（可选）"
    )
    parser.add_argument(
        "--no-ingest",
        action="store_true",
        help="只提取内容，不导入知识库"
    )
    parser.add_argument(
        "--save-md",
        help="保存提取结果为 Markdown 文件（可选）"
    )
    
    args = parser.parse_args()
    
    try:
        # 处理图片
        documents = process_image_folder(
            args.folder,
            output_format=args.format,
            custom_prompt=args.prompt
        )
        
        if not documents:
            print("\n没有成功提取任何内容")
            return
        
        # 保存为 Markdown（可选）
        if args.save_md:
            output_path = Path(args.save_md)
            with open(output_path, 'w', encoding='utf-8') as f:
                for doc in documents:
                    f.write(doc['content'])
                    f.write("\n\n")
            print(f"\n✓ 已保存到: {output_path}")
        
        # 导入知识库（可选）
        if not args.no_ingest:
            print("\n开始导入知识库...")
            config = load_config()
            writer = QdrantWriter(config)
            
            for doc in documents:
                writer.add_document(
                    content=doc['content'],
                    metadata=doc['metadata']
                )
            
            print(f"✓ 已导入 {len(documents)} 个文档到知识库")
        
        print("\n✅ 完成！")
        
    except Exception as e:
        print(f"\n❌ 错误: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
