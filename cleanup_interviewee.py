"""
删除单个受访者的访谈记录
用法：python cleanup_interviewee.py <项目名称> <受访者名称>
例如：python cleanup_interviewee.py demo_research participant_01
"""
import sys
from pathlib import Path
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue

QDRANT_PATH = "./qdrant_data"
COLLECTION = "personal_kb"
VAULT_PATH = "./vault"

if len(sys.argv) < 3:
    print("用法: python cleanup_interviewee.py <项目名称> <受访者名称>")
    print("例如: python cleanup_interviewee.py demo_research participant_01")
    sys.exit(1)

project_name = sys.argv[1]
interviewee_name = sys.argv[2]

print(f"\n{'='*60}")
print(f"删除受访者记录")
print(f"项目: {project_name}")
print(f"受访者: {interviewee_name}")
print(f"{'='*60}\n")

# 1. 删除 Qdrant 中的记录
print("Step 1: 删除 Qdrant 记录...")
client = QdrantClient(path=QDRANT_PATH)

try:
    result = client.delete(
        collection_name=COLLECTION,
        points_selector=Filter(
            must=[
                FieldCondition(
                    key="project",
                    match=MatchValue(value=project_name)
                ),
                FieldCondition(
                    key="interviewee",
                    match=MatchValue(value=interviewee_name)
                )
            ]
        )
    )
    print(f"  ✓ Qdrant 删除完成: {result}")
except Exception as e:
    print(f"  ✗ Qdrant 删除失败: {e}")

# 2. 删除 Obsidian 文件
print("\nStep 2: 删除 Obsidian 文件...")
interview_folder = Path(VAULT_PATH) / "50-interviews"

if not interview_folder.exists():
    print(f"  ⊘ 文件夹不存在: {interview_folder}")
else:
    deleted_count = 0
    for md_file in interview_folder.glob("*.md"):
        try:
            content = md_file.read_text(encoding="utf-8", errors="ignore")
            if f"project: {project_name}" in content and f"interviewee: {interviewee_name}" in content:
                md_file.unlink()
                deleted_count += 1
                print(f"  ✓ 删除: {md_file.name}")
        except Exception as e:
            print(f"  ✗ 删除失败 {md_file.name}: {e}")
    
    if deleted_count == 0:
        print(f"  ⊘ 未找到匹配的文件")
    else:
        print(f"\n  总计删除 {deleted_count} 个文件")

print(f"\n{'='*60}")
print("清理完成")
print(f"{'='*60}\n")
