"""
删除指定文件的入库记录
用法：python delete_entry.py "文件名（不含路径）"
例如：python delete_entry.py "Sensory_Intelligence_chat.txt"
"""
import sys
import os
from pathlib import Path
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue

QDRANT_PATH  = "./qdrant_data"
COLLECTION   = "personal_kb"
VAULT_PATH   = Path(os.environ.get("OBSIDIAN_VAULT_PATH", "vault"))

filename = sys.argv[1] if len(sys.argv) > 1 else input("要删除的源文件名：")

# 1. 删除 Qdrant 里的 chunks
client = QdrantClient(path=QDRANT_PATH)
result = client.delete(
    collection_name=COLLECTION,
    points_selector=Filter(
        must=[FieldCondition(
            key="source_file",
            match=MatchValue(value=filename)
        )]
    )
)
print(f"Qdrant 删除完成：{result}")

# 2. 在 vault 里找并删除对应的 .md 文件
deleted_md = []
for md_file in Path(VAULT_PATH).rglob("*.md"):
    content = md_file.read_text(encoding="utf-8", errors="ignore")
    if f"source_file: {filename}" in content:
        md_file.unlink()
        deleted_md.append(str(md_file))
        print(f"已删除 Obsidian 文件：{md_file}")

if not deleted_md:
    print("未找到对应的 Obsidian .md 文件（可能需要手动删除）")

print("完成")
