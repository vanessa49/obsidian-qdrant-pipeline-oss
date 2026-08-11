"""
重新处理单个转录稿
用法：python retry_single_transcript.py <转录稿路径> <项目名称> [大纲路径]
例如：python retry_single_transcript.py "kb-inbox/demo/participant_01.txt" "demo_research" "kb-inbox/demo/guide.docx"
"""
import sys
from pathlib import Path
import yaml

from interview_processor import process_with_guide, process_transcript_only
from obsidian_writer import ObsidianWriter
from qdrant_writer import QdrantWriter

def load_config():
    """加载配置"""
    with open("config.yaml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

if len(sys.argv) < 3:
    print("用法: python retry_single_transcript.py <转录稿路径> <项目名称> [大纲路径]")
    print("例如: python retry_single_transcript.py kb-inbox/demo/participant_01.txt demo_research kb-inbox/demo/guide.docx")
    sys.exit(1)

transcript_path = sys.argv[1]
project_name = sys.argv[2]
guide_path = sys.argv[3] if len(sys.argv) > 3 else None

print(f"\n{'='*60}")
print(f"重新处理转录稿")
print(f"{'='*60}")
print(f"转录稿: {transcript_path}")
print(f"项目: {project_name}")
print(f"大纲: {guide_path if guide_path else '无'}")
print(f"{'='*60}\n")

# 加载配置
config = load_config()
vault_path = config.get("vault_path")
qdrant_config = config.get("qdrant", {"path": "./qdrant_data"})
ollama_url = config.get("ollama", {}).get("url", "http://localhost:11434")

# 处理转录稿
if guide_path:
    chunks = process_with_guide(transcript_path, guide_path, project_name)
else:
    chunks = process_transcript_only(transcript_path, project_name)

if not chunks:
    print("\n✗ 处理失败，未生成任何chunks")
    sys.exit(1)

print(f"\n{'='*60}")
print(f"写入 Obsidian 和 Qdrant")
print(f"{'='*60}\n")

# 初始化写入器
obsidian_writer = ObsidianWriter(vault_path)
qdrant_writer = QdrantWriter(qdrant_config, ollama_url)

# 写入
for idx, chunk_data in enumerate(chunks):
    chunk_text = chunk_data["text"]
    metadata = chunk_data["metadata"]
    
    # 判断是否有受访者信息
    if "interviewee" in metadata:
        title = f"{project_name}-{metadata['interviewee']}"
        source_filename = f"{title}.md"
    else:
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
    
    if "interviewee" in metadata:
        frontmatter["interviewee"] = metadata["interviewee"]
        frontmatter["qa_count"] = metadata.get("qa_count", 0)
    
    # 写入 Obsidian
    obs_success, obs_result = obsidian_writer.write(
        chunk_text, frontmatter, source_filename
    )
    
    if not obs_success:
        print(f"  ✗ Obsidian写入失败: {obs_result}")
        continue
    
    obsidian_path = obs_result
    print(f"  ✓ Obsidian: {obsidian_path}")
    
    # 写入 Qdrant
    qd_success, qd_result = qdrant_writer.upsert(
        chunk_text, frontmatter, obsidian_path, source_filename
    )
    
    if qd_success:
        print(f"  ✓ Qdrant: {qd_result}")
    else:
        print(f"  ✗ Qdrant失败: {qd_result}")

print(f"\n{'='*60}")
print("处理完成")
print(f"{'='*60}\n")
