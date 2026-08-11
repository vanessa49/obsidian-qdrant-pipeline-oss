"""
主流程 - 文档入库管道
支持单文件处理和批量监控模式
从 config.yaml 读取配置，命令行参数可覆盖
"""

import argparse
import shutil
import time
from pathlib import Path
from typing import Optional

import yaml
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from compress import compress_raw_material, get_source_type, is_raw_material, needs_compression
from convert import convert_to_markdown, ConversionError
from interview_processor import (
    determine_processing_path,
    process_keypoints,
    process_transcript_only,
    process_with_guide,
    scan_project,
)
from obsidian_writer import ObsidianWriter
from qdrant_writer import QdrantWriter
from structure import structure_document


def load_config(config_path: str = "config.yaml") -> dict:
    """
    加载配置文件，返回配置字典
    文件不存在时返回空字典（调用方负责提供默认值）
    """
    path = Path(config_path)
    if path.exists():
        with open(path, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    return {}


class DocumentProcessor:
    """文档处理器"""
    
    # 支持的文件扩展名
    SUPPORTED_EXTENSIONS = {'.pdf', '.pptx', '.docx', '.html', '.htm', '.md', '.txt', '.tex'}
    
    def __init__(self, vault_path: str, qdrant_config: dict,
                 ollama_url: str = "http://localhost:11434"):
        """
        初始化文档处理器

        Args:
            vault_path: Obsidian vault 路径
            qdrant_config: Qdrant 配置字典，含 url 或 path 键
            ollama_url: Ollama 服务地址
        """
        self.obsidian_writer = ObsidianWriter(vault_path)
        self.qdrant_writer = QdrantWriter(qdrant_config, ollama_url)
    
    def process_file(self, file_path: Path) -> tuple[str, Optional[str]]:
        """
        处理单个文件
        
        Args:
            file_path: 文件路径
            
        Returns:
            (状态, 详细信息)
            状态: SUCCESS / SKIP / FAILED
        """
        print(f"\n{'='*60}")
        print(f"处理文件: {file_path.name}")
        print(f"{'='*60}")
        
        try:
            # Step 1: 转换为 Markdown
            print("Step 1/5: 转换为 Markdown...")
            markdown_content = convert_to_markdown(str(file_path))
            print(f"  ✓ 转换成功 ({len(markdown_content)} 字符)")
            
            # Step 2: 原始素材检测和压缩（新增）
            print("Step 2/5: 检测原始素材...")
            extra_meta = {}
            if is_raw_material(str(file_path), markdown_content):
                source_type = get_source_type(str(file_path))
                print(f"  → 检测为原始素材（{source_type}）")
                
                # 判断是否需要压缩
                if needs_compression(markdown_content):
                    print(f"  → 内容较长，执行压缩...")
                    markdown_content, extra_meta = compress_raw_material(
                        markdown_content, source_type, file_path.name
                    )
                    print(f"  ✓ 压缩完成")
                else:
                    # 短文件直接打标签，不压缩
                    print(f"  → 内容较短，跳过压缩，仅打标签")
                    extra_meta = {
                        "tier": "raw_material",
                        "compressed": False,
                        "source_length": len(markdown_content),
                        "source_type": source_type
                    }
            else:
                print(f"  ⊘ 非原始素材，跳过压缩")
            
            # Step 3: 结构化文档
            print("Step 3/5: 生成 frontmatter...")
            frontmatter = structure_document(markdown_content, file_path.name)
            
            # 合并额外字段（新增）
            frontmatter.update(extra_meta)
            
            # Step 4: 写入 Obsidian
            print("Step 4/5: 写入 Obsidian vault...")
            obs_success, obs_result = self.obsidian_writer.write(
                markdown_content, frontmatter, file_path.name
            )
            
            if not obs_success:
                if obs_result.startswith("SKIP"):
                    print(f"  ⊘ {obs_result}")
                    return "SKIP", obs_result
                else:
                    print(f"  ✗ {obs_result}")
                    return "FAILED", obs_result
            
            print(f"  ✓ 写入成功: {obs_result}")
            obsidian_path = obs_result
            
            # Step 5: 写入 Qdrant
            print("Step 5/5: 写入 Qdrant...")
            qd_success, qd_result = self.qdrant_writer.upsert(
                markdown_content, frontmatter, obsidian_path, file_path.name
            )
            
            if not qd_success:
                print(f"  ✗ {qd_result}")
                return "FAILED", f"Obsidian 成功，Qdrant 失败: {qd_result}"
            
            print(f"  ✓ {qd_result}")
            
            print(f"\n{'='*60}")
            print(f"✓ SUCCESS: {file_path.name}")
            print(f"{'='*60}")
            
            return "SUCCESS", obsidian_path
            
        except ConversionError as e:
            error_msg = f"转换失败: {e}"
            print(f"  ✗ {error_msg}")
            print(f"\n{'='*60}")
            print(f"✗ FAILED: {file_path.name}")
            print(f"{'='*60}")
            return "FAILED", error_msg
            
        except Exception as e:
            error_msg = f"处理失败: {e}"
            print(f"  ✗ {error_msg}")
            print(f"\n{'='*60}")
            print(f"✗ FAILED: {file_path.name}")
            print(f"{'='*60}")
            return "FAILED", error_msg
    
    def is_supported_file(self, file_path: Path) -> bool:
        """检查文件是否支持"""
        return file_path.suffix.lower() in self.SUPPORTED_EXTENSIONS


class InboxWatcher(FileSystemEventHandler):
    """文件夹监控器"""
    
    def __init__(self, inbox_path: Path, processor: DocumentProcessor):
        """
        初始化监控器
        
        Args:
            inbox_path: 监控的文件夹路径
            processor: 文档处理器
        """
        self.inbox_path = inbox_path
        self.processor = processor
        self.processed_folder = inbox_path / "processed"
        self.failed_folder = inbox_path / "failed"
        
        # 创建子文件夹
        self.processed_folder.mkdir(exist_ok=True)
        self.failed_folder.mkdir(exist_ok=True)
    
    def on_created(self, event):
        """文件创建事件"""
        if event.is_directory:
            return
        
        file_path = Path(event.src_path)
        
        # 忽略子文件夹中的文件
        if self.processed_folder in file_path.parents or self.failed_folder in file_path.parents:
            return
        
        # 检查是否支持
        if not self.processor.is_supported_file(file_path):
            print(f"忽略不支持的文件: {file_path.name}")
            return
        
        # 等待文件写入完成
        time.sleep(1)
        
        # 处理文件
        self._process_and_move(file_path)
    
    def _process_and_move(self, file_path: Path):
        """处理文件并移动到对应文件夹"""
        status, detail = self.processor.process_file(file_path)
        
        if status == "SUCCESS":
            # 移动到 processed 文件夹
            target_path = self.processed_folder / file_path.name
            shutil.move(str(file_path), str(target_path))
            print(f"✓ 文件已移动到: {target_path}")
            
        elif status == "SKIP":
            # 也移动到 processed 文件夹
            target_path = self.processed_folder / file_path.name
            shutil.move(str(file_path), str(target_path))
            print(f"⊘ 文件已移动到: {target_path}")
            
        else:  # FAILED
            # 移动到 failed 文件夹
            target_path = self.failed_folder / file_path.name
            shutil.move(str(file_path), str(target_path))
            
            # 写入错误信息
            error_file = self.failed_folder / f"{file_path.stem}.error.txt"
            error_file.write_text(detail or "未知错误", encoding='utf-8')
            
            print(f"✗ 文件已移动到: {target_path}")
            print(f"✗ 错误信息已写入: {error_file}")
    
    def process_existing_files(self):
        """处理文件夹中已有的文件"""
        print(f"\n扫描现有文件: {self.inbox_path}")
        
        files = [f for f in self.inbox_path.iterdir() 
                if f.is_file() and self.processor.is_supported_file(f)]
        
        if not files:
            print("没有找到待处理的文件")
            return
        
        print(f"找到 {len(files)} 个文件待处理\n")
        
        for file_path in files:
            self._process_and_move(file_path)


def process_single_file(file_path: str, vault_path: str,
                        qdrant_config: dict, ollama_url: str):
    """单文件处理模式"""
    file = Path(file_path)
    
    if not file.exists():
        print(f"错误: 文件不存在 - {file_path}")
        return
    
    processor = DocumentProcessor(vault_path, qdrant_config, ollama_url)
    
    if not processor.is_supported_file(file):
        print(f"错误: 不支持的文件类型 - {file.suffix}")
        return
    
    status, detail = processor.process_file(file)
    
    if status == "SUCCESS":
        print(f"\n✓ 处理成功")
    elif status == "SKIP":
        print(f"\n⊘ 跳过: {detail}")
    else:
        print(f"\n✗ 处理失败: {detail}")


def watch_folder(inbox_path: str, vault_path: str,
                 qdrant_config: dict, ollama_url: str):
    """文件夹监控模式"""
    inbox = Path(inbox_path)
    
    if not inbox.exists():
        print(f"错误: 文件夹不存在 - {inbox_path}")
        return
    
    processor = DocumentProcessor(vault_path, qdrant_config, ollama_url)
    watcher = InboxWatcher(inbox, processor)
    
    # 处理现有文件
    watcher.process_existing_files()
    
    # 启动监控
    observer = Observer()
    observer.schedule(watcher, str(inbox), recursive=False)
    observer.start()
    
    print(f"\n{'='*60}")
    print(f"开始监控文件夹: {inbox_path}")
    print(f"按 Ctrl+C 停止监控")
    print(f"{'='*60}\n")
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n停止监控...")
        observer.stop()
    
    observer.join()
    print("监控已停止")


def process_interview_project(project_folder: str, vault_path: str,
                               qdrant_config: dict, ollama_url: str):
    """访谈项目批量处理模式"""
    print(f"\n{'='*60}")
    print(f"访谈项目批量入库")
    print(f"{'='*60}\n")
    
    # Step 1: 扫描项目文件夹
    print("Step 1: 扫描项目文件夹...")
    try:
        scan_result = scan_project(project_folder)
    except Exception as e:
        print(f"✗ 扫描失败: {e}")
        return
    
    # Step 2: 显示扫描结果
    print(f"\n扫描结果:")
    print(f"  大纲: {Path(scan_result['guide']).name if scan_result['guide'] else '无'}")
    print(f"  关键点: {Path(scan_result['keypoints']).name if scan_result['keypoints'] else '无'}")
    print(f"  转录稿: {len(scan_result['transcripts'])} 个")
    
    if not scan_result['keypoints'] and not scan_result['transcripts']:
        print("\n✗ 错误: 未找到可处理的文件（需要关键点文件或转录稿）")
        return
    
    # Step 3: 确定处理路径
    path, desc = determine_processing_path(scan_result)
    print(f"\n将使用路径{path}: {desc}")
    
    # Step 4: 用户确认
    confirm = input("\n继续？(y/n): ").strip().lower()
    if confirm != 'y':
        print("已取消")
        return
    
    # Step 5: 处理文件
    project_name = Path(project_folder).name
    
    obsidian_writer = ObsidianWriter(vault_path)
    qdrant_writer = QdrantWriter(qdrant_config, ollama_url)
    
    all_chunks = []
    
    # 路径A: 处理关键点文件
    if scan_result['keypoints']:
        try:
            chunks = process_keypoints(scan_result['keypoints'], project_name)
            all_chunks.extend(chunks)
        except Exception as e:
            print(f"✗ 处理关键点文件失败: {e}")
    
    # 路径B/C: 处理转录稿
    for transcript_path in scan_result['transcripts']:
        try:
            if scan_result['guide'] and not scan_result['keypoints']:
                # 路径B: 有大纲
                chunks = process_with_guide(transcript_path, scan_result['guide'], project_name)
            else:
                # 路径C: 无大纲
                chunks = process_transcript_only(transcript_path, project_name)
            
            all_chunks.extend(chunks)
        except Exception as e:
            print(f"✗ 处理转录稿失败 {Path(transcript_path).name}: {e}")
    
    if not all_chunks:
        print("\n✗ 没有成功处理任何内容")
        return
    
    print(f"\n{'='*60}")
    print(f"Step 6: 写入 Obsidian 和 Qdrant")
    print(f"{'='*60}")
    print(f"总计 {len(all_chunks)} 个chunks待写入\n")
    
    # Step 6: 写入 Obsidian 和 Qdrant
    success_count = 0
    failed_count = 0
    
    for idx, chunk_data in enumerate(all_chunks):
        chunk_text = chunk_data["text"]
        metadata = chunk_data["metadata"]
        
        # 判断是否有受访者信息（横向表格）
        if "interviewee" in metadata:
            # 每个受访者一个文档
            title = f"{project_name}-{metadata['interviewee']}"
            source_filename = f"{title}.md"
        else:
            # 传统方式：每个chunk一个文档
            title = f"{project_name}-{metadata['source_type']}-{metadata.get('chunk_index', idx)}"
            source_filename = f"{project_name}-chunk{idx}.md"
        
        # 构建 frontmatter
        frontmatter = {
            "title": title,
            "type": "interview",
            "project": metadata["project"],
            "source_type": metadata["source_type"],
            "tier": metadata["tier"],
            "tags": ["interview", project_name]
        }
        
        # 添加受访者信息（如果有）
        if "interviewee" in metadata:
            frontmatter["interviewee"] = metadata["interviewee"]
            frontmatter["qa_count"] = metadata.get("qa_count", 0)
        
        # 写入 Obsidian（使用项目子文件夹）
        obs_success, obs_result = obsidian_writer.write(
            chunk_text, frontmatter, source_filename
        )
        
        if not obs_success:
            if "SKIP" in obs_result:
                print(f"  ⊘ {title}: 已存在")
            else:
                print(f"  ✗ {title}: Obsidian写入失败 - {obs_result}")
                failed_count += 1
            continue
        
        obsidian_path = obs_result
        
        # 写入 Qdrant
        qd_success, qd_result = qdrant_writer.upsert(
            chunk_text, frontmatter, obsidian_path, source_filename
        )
        
        if not qd_success:
            print(f"  ✗ {title}: Qdrant写入失败 - {qd_result}")
            failed_count += 1
        else:
            success_count += 1
            print(f"  ✓ {title}")
    
    # 最终报告
    print(f"\n{'='*60}")
    print(f"处理完成")
    print(f"{'='*60}")
    print(f"✓ 成功: {success_count} 个文档")
    print(f"✗ 失败: {failed_count} 个文档")
    print(f"{'='*60}\n")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="个人知识库自动化入库管道",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 单文件处理（从 config.yaml 读取配置）
  python ingest.py --file document.pdf

  # 单文件处理（命令行覆盖 vault 路径）
  python ingest.py --file document.pdf --vault <VAULT_PATH>

  # 批量监控文件夹
  python ingest.py --watch <INBOX_PATH>
        """
    )
    
    # 模式选择
    mode_group = parser.add_mutually_exclusive_group(required=True)
    mode_group.add_argument('--file', type=str, help='单文件处理模式：指定文件路径')
    mode_group.add_argument('--watch', type=str, help='批量监控模式：指定监控文件夹路径')
    mode_group.add_argument('--interview', type=str, help='访谈项目批量入库：指定项目文件夹路径')
    
    # 可选覆盖参数（不指定则从 config.yaml 读取）
    parser.add_argument('--vault', type=str, help='Obsidian vault 路径（覆盖 config.yaml）')
    parser.add_argument('--qdrant', type=str, help='Qdrant URL（覆盖 config.yaml，仅 url 模式）')
    parser.add_argument('--ollama', type=str, help='Ollama 服务地址（覆盖 config.yaml）')
    parser.add_argument('--config', type=str, default='config.yaml',
                        help='配置文件路径 (默认: config.yaml)')
    
    args = parser.parse_args()
    
    # 加载配置文件
    cfg = load_config(args.config)
    
    # 解析各项配置（命令行 > config.yaml > 硬编码默认值）
    vault_path = args.vault or cfg.get("vault_path")
    if not vault_path:
        print("错误: 未指定 vault 路径，请在 config.yaml 设置 vault_path 或使用 --vault 参数")
        return
    
    ollama_url = args.ollama or cfg.get("ollama", {}).get("url", "http://localhost:11434")
    
    # 构建 qdrant_config dict
    if args.qdrant:
        # 命令行传入的一定是 URL
        qdrant_config = {"url": args.qdrant}
    else:
        qdrant_config = cfg.get("qdrant", {"url": "http://127.0.0.1:6333"})
    
    # 根据模式执行
    if args.file:
        process_single_file(args.file, vault_path, qdrant_config, ollama_url)
    elif args.interview:
        process_interview_project(args.interview, vault_path, qdrant_config, ollama_url)
    else:
        inbox = args.watch or cfg.get("inbox_path")
        if not inbox:
            print("错误: 未指定监控文件夹，请在 config.yaml 设置 inbox_path 或使用 --watch 参数")
            return
        watch_folder(inbox, vault_path, qdrant_config, ollama_url)


if __name__ == "__main__":
    main()
