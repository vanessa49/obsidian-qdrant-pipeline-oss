"""
修复 marker-pdf 模型缓存问题
手动下载所有必需文件，绕过 surya 的有问题的下载逻辑
"""

from pathlib import Path
from huggingface_hub import hf_hub_download
import sys

# 模型仓库信息
# 通过测试发现 surya 使用的是 vikp/layout_model
REPO_ID = "vikp/layout_model"
REVISION = "main"  # 或者尝试 "2025_09_23" 如果有这个分支

# 缓存目录
cache_base = Path.home() / "AppData/Local/datalab/datalab/Cache/models/layout/2025_09_23"
cache_base.mkdir(parents=True, exist_ok=True)

print(f"目标目录: {cache_base}")
print(f"仓库: {REPO_ID}")
print(f"="*60)

# 需要下载的文件列表（根据日志提取）
FILES_TO_DOWNLOAD = [
    "config.json",
    "preprocessor_config.json",
    "processor_config.json",
    "tokenizer_config.json",
    "special_tokens_map.json",
    "vocab_math.json",
    "specials.json",
    "specials_dict.json",
    "training_args.bin",
    "model.safetensors",
    "README.md",
    ".gitattributes",
    "manifest.json",
]

print("开始下载文件...\n")

success_count = 0
failed_files = []

for filename in FILES_TO_DOWNLOAD:
    target_file = cache_base / filename
    
    # 检查文件是否已存在且完整
    if target_file.exists():
        size = target_file.stat().st_size
        
        # model.safetensors 应该大于 1GB
        if filename == "model.safetensors" and size < 1_000_000_000:
            print(f"⚠ {filename}: 文件不完整 ({size:,} bytes)，重新下载...")
        else:
            print(f"✓ {filename}: 已存在 ({size:,} bytes)，跳过")
            success_count += 1
            continue
    
    # 下载文件
    try:
        print(f"⬇ {filename}: 下载中...", end="", flush=True)
        
        downloaded_path = hf_hub_download(
            repo_id=REPO_ID,
            filename=filename,
            revision=REVISION,
            cache_dir=str(cache_base.parent.parent.parent),  # HF 缓存根目录
            local_dir=str(cache_base),
            local_dir_use_symlinks=False,
        )
        
        size = Path(downloaded_path).stat().st_size
        print(f" ✓ 完成 ({size:,} bytes)")
        success_count += 1
        
    except Exception as e:
        print(f" ✗ 失败: {e}")
        failed_files.append(filename)

# 总结
print("\n" + "="*60)
print("下载总结:")
print(f"  成功: {success_count}/{len(FILES_TO_DOWNLOAD)}")
if failed_files:
    print(f"  失败: {failed_files}")
print("="*60)

# 验证
print("\n最终文件列表:")
if cache_base.exists():
    files = sorted(cache_base.iterdir())
    for f in files:
        if f.is_file():
            size = f.stat().st_size
            print(f"  ✓ {f.name}: {size:,} bytes")
    
    # 检查核心文件
    model_file = cache_base / "model.safetensors"
    config_file = cache_base / "config.json"
    
    if model_file.exists() and model_file.stat().st_size > 1_000_000_000:
        if config_file.exists():
            print(f"\n✅ 模型缓存完整，可以使用！")
            sys.exit(0)
        else:
            print(f"\n⚠ 缺少 config.json")
            sys.exit(1)
    else:
        print(f"\n⚠ model.safetensors 不完整或缺失")
        sys.exit(1)
else:
    print("✗ 目录不存在")
    sys.exit(1)
