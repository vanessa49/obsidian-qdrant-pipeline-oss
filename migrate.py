"""
Obsidian Vault 迁移脚本 - 将已有的 .md 文件推入 Qdrant
不修改 Obsidian 文件，只读取内容并写入向量数据库
"""

import argparse
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

import yaml

from qdrant_writer import QdrantWriter


def load_config(config_path: str = "config.yaml") -> dict:
    path = Path(config_path)
    if path.exists():
        with open(path, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    return {}


class MigrationStats:
    """迁移统计"""
    
    def __init__(self):
        self.total = 0
        self.success = 0
        self.skipped = 0
        self.failed = 0
        self.errors: List[Tuple[str, str]] = []  # (文件路径, 错误信息)
    
    def add_success(self):
        self.success += 1
    
    def add_skipped(self):
        self.skipped += 1
    
    def add_failed(self, file_path: str, error: str):
        self.failed += 1
        self.errors.append((file_path, error))
    
    def print_summary(self):
        """打印汇总信息"""
        print("\n" + "="*60)
        print("迁移完成")
        print("="*60)
        print(f"扫描文件：{self.total} 个")
        print(f"成功写入：{self.success} 个")
        print(f"已存在跳过：{self.skipped} 个")
        print(f"失败：{self.failed} 个")
        
        if self.failed > 0:
            print(f"  （详见 migrate_errors.log）")
        
        if self.total > 0:
            coverage = ((self.success + self.skipped) / self.total) * 100
            print(f"预计检索覆盖：{coverage:.0f}%")
        
        print("="*60)


def parse_frontmatter(content: str) -> Tuple[Dict, str]:
    """
    解析 Markdown 文件的 frontmatter
    
    Args:
        content: 文件内容
        
    Returns:
        (frontmatter 字典, 正文内容)
    """
    # 检查是否有 frontmatter
    if not content.startswith('---'):
        return {}, content
    
    # 查找第二个 ---
    parts = content.split('---', 2)
    
    if len(parts) < 3:
        return {}, content
    
    frontmatter_str = parts[1].strip()
    body = parts[2].strip()
    
    # 解析 YAML
    try:
        frontmatter = yaml.safe_load(frontmatter_str)
        if not isinstance(frontmatter, dict):
            return {}, content
        return frontmatter, body
    except Exception:
        # YAML 解析失败，返回空字典
        return {}, content


def complete_frontmatter(frontmatter: Dict, file_path: Path) -> Dict:
    """
    补全缺失的 frontmatter 字段
    
    Args:
        frontmatter: 原始 frontmatter
        file_path: 文件路径
        
    Returns:
        补全后的 frontmatter
    """
    completed = frontmatter.copy()
    
    # 补全 title
    if 'title' not in completed or not completed['title']:
        completed['title'] = file_path.stem
    
    # 补全 type
    if 'type' not in completed:
        completed['type'] = 'reference'
    
    # 补全 tags
    if 'tags' not in completed:
        completed['tags'] = []
    elif not isinstance(completed['tags'], list):
        # 如果 tags 不是列表，转换为列表
        completed['tags'] = [str(completed['tags'])]
    
    # 补全 tier
    if 'tier' not in completed:
        completed['tier'] = 'processed'
    
    # 补全 source_type
    if 'source_type' not in completed:
        completed['source_type'] = ''
    
    # 补全 date_added（如果没有，使用文件修改时间）
    if 'date_added' not in completed:
        try:
            mtime = file_path.stat().st_mtime
            completed['date_added'] = datetime.fromtimestamp(mtime).strftime('%Y-%m-%d')
        except Exception:
            completed['date_added'] = datetime.now().strftime('%Y-%m-%d')
    
    return completed


def get_obsidian_relative_path(vault_path: Path, file_path: Path) -> str:
    """
    获取文件在 Obsidian vault 中的相对路径
    
    Args:
        vault_path: vault 根路径
        file_path: 文件绝对路径
        
    Returns:
        相对路径字符串
    """
    try:
        return str(file_path.relative_to(vault_path))
    except ValueError:
        return str(file_path)


def migrate_file(
    file_path: Path,
    vault_path: Path,
    writer: QdrantWriter,
    stats: MigrationStats,
) -> bool:
    """
    迁移单个文件

    Args:
        file_path: 文件路径
        vault_path: vault 根路径
        writer: Qdrant 写入器
        stats: 统计对象

    Returns:
        是否成功
    """
    try:
        # 读取文件内容
        content = file_path.read_text(encoding='utf-8')

        # 解析 frontmatter
        frontmatter, body = parse_frontmatter(content)

        # 补全 frontmatter
        frontmatter = complete_frontmatter(frontmatter, file_path)

        # 如果正文为空，跳过
        if not body.strip():
            print(f"  ⊘ 跳过（正文为空）: {file_path.name}")
            stats.add_skipped()
            return True

        # 获取相对路径
        obsidian_path = get_obsidian_relative_path(vault_path, file_path)

        # 写入 Qdrant
        success, result = writer.upsert(
            body,
            frontmatter,
            obsidian_path,
            file_path.name
        )

        if success:
            if "跳过" in result or "SKIP" in result:
                print(f"  ⊘ {result}: {file_path.name}")
                stats.add_skipped()
            else:
                print(f"  ✓ {result}: {file_path.name}")
                stats.add_success()
            return True
        else:
            print(f"  ✗ 失败: {file_path.name} - {result}")
            stats.add_failed(str(file_path), result)
            return False

    except Exception as e:
        error_msg = f"处理失败: {str(e)}"
        print(f"  ✗ {error_msg}: {file_path.name}")
        stats.add_failed(str(file_path), error_msg)
        return False


def find_markdown_files(vault_path: Path, exclude_folders: List[str]) -> List[Path]:
    """
    查找所有 Markdown 文件
    
    Args:
        vault_path: vault 根路径
        exclude_folders: 排除的文件夹列表
        
    Returns:
        Markdown 文件路径列表
    """
    md_files = []
    
    for md_file in vault_path.rglob('*.md'):
        # 检查是否在排除文件夹中
        relative_path = md_file.relative_to(vault_path)
        
        # 检查路径的任何部分是否在排除列表中
        should_exclude = False
        for part in relative_path.parts:
            if part in exclude_folders:
                should_exclude = True
                break
        
        if not should_exclude:
            md_files.append(md_file)
    
    return md_files


def write_error_log(stats: MigrationStats):
    """写入错误日志"""
    if not stats.errors:
        return
    
    log_path = Path("migrate_errors.log")
    
    with open(log_path, 'w', encoding='utf-8') as f:
        f.write("迁移错误日志\n")
        f.write("="*60 + "\n\n")
        
        for file_path, error in stats.errors:
            f.write(f"文件: {file_path}\n")
            f.write(f"错误: {error}\n")
            f.write("-"*60 + "\n\n")
    
    print(f"\n错误日志已写入: {log_path}")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="将 Obsidian vault 中的 Markdown 文件迁移到 Qdrant",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 从 config.yaml 读取配置，正常迁移
  python migrate.py

  # 指定 vault 路径
  python migrate.py --vault <VAULT_PATH>

  # Dry-run 模式（只统计，不写入）
  python migrate.py --dry-run

  # 命令行覆盖 Qdrant 地址（url 模式）
  python migrate.py --qdrant http://127.0.0.1:6333
        """
    )

    parser.add_argument('--vault', type=str,
                        help='Obsidian vault 路径（覆盖 config.yaml）')
    parser.add_argument('--qdrant', type=str,
                        help='Qdrant URL（覆盖 config.yaml，仅 url 模式）')
    parser.add_argument('--ollama', type=str,
                        help='Ollama 服务地址（覆盖 config.yaml）')
    parser.add_argument('--config', type=str, default='config.yaml',
                        help='配置文件路径 (默认: config.yaml)')
    parser.add_argument('--dry-run', action='store_true',
                        help='Dry-run 模式：只统计，不写入 Qdrant')
    parser.add_argument('--exclude', type=str, nargs='+',
                        default=['00-inbox'],
                        help='排除的文件夹列表 (默认: 00-inbox)')

    args = parser.parse_args()

    # 加载配置文件
    cfg = load_config(args.config)

    # 解析各项配置（命令行 > config.yaml > 硬编码默认值）
    vault_path_str = args.vault or cfg.get("vault_path")
    if not vault_path_str:
        print("错误: 未指定 vault 路径，请在 config.yaml 设置 vault_path 或使用 --vault 参数")
        return

    vault_path = Path(vault_path_str)
    if not vault_path.exists():
        print(f"错误: Vault 路径不存在 - {vault_path_str}")
        return

    ollama_url = args.ollama or cfg.get("ollama", {}).get("url", "http://localhost:11434")

    if args.qdrant:
        qdrant_config = {"url": args.qdrant}
    else:
        qdrant_config = cfg.get("qdrant", {"url": "http://127.0.0.1:6333"})

    print("="*60)
    print("Obsidian Vault 迁移到 Qdrant")
    print("="*60)
    print(f"Vault 路径: {vault_path}")
    if "path" in qdrant_config:
        print(f"Qdrant 本地路径: {qdrant_config['path']}")
    else:
        print(f"Qdrant 地址: {qdrant_config.get('url')}")
    print(f"排除文件夹: {', '.join(args.exclude)}")
    if args.dry_run:
        print("模式: DRY-RUN（只统计，不写入）")
    print("="*60)

    # 查找所有 Markdown 文件
    print("\n扫描 Markdown 文件...")
    md_files = find_markdown_files(vault_path, args.exclude)

    if not md_files:
        print("未找到任何 Markdown 文件")
        return

    print(f"找到 {len(md_files)} 个 Markdown 文件\n")

    # 初始化统计
    stats = MigrationStats()
    stats.total = len(md_files)

    # Dry-run 模式：只统计
    if args.dry_run:
        print("Dry-run 模式：预览文件列表\n")
        for md_file in md_files[:10]:
            print(f"  - {md_file.relative_to(vault_path)}")
        if len(md_files) > 10:
            print(f"  ... 还有 {len(md_files) - 10} 个文件")

        estimated_time = len(md_files) * 2
        print(f"\n预计处理 {len(md_files)} 个文件")
        print(f"预计耗时: {estimated_time // 60} 分 {estimated_time % 60} 秒")

        stats.success = len(md_files)
        stats.print_summary()
        return

    # 初始化 Qdrant 写入器
    print("初始化 Qdrant 写入器...")
    try:
        writer = QdrantWriter(qdrant_config, ollama_url)
        print("  ✓ Qdrant 连接成功\n")
    except Exception as e:
        print(f"  ✗ Qdrant 连接失败: {e}")
        return

    # 开始迁移
    print("开始迁移...\n")
    start_time = time.time()

    for idx, md_file in enumerate(md_files, 1):
        print(f"[{idx}/{len(md_files)}] {md_file.name}")
        migrate_file(md_file, vault_path, writer, stats)

    elapsed_time = time.time() - start_time
    print(f"\n总耗时: {int(elapsed_time // 60)} 分 {int(elapsed_time % 60)} 秒")

    if stats.errors:
        write_error_log(stats)

    stats.print_summary()


if __name__ == "__main__":
    main()
