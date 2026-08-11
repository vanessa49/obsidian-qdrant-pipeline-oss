"""
强制下载 marker-pdf 模型
单进程，无并发，最简单的下载逻辑
"""

from pathlib import Path
import shutil
import sys

# 1. 删除旧缓存
cache_dir = Path.home() / "AppData/Local/datalab/datalab/Cache"
print(f"缓存目录: {cache_dir}")

if cache_dir.exists():
    print("\n是否删除旧缓存？这将删除所有已下载的模型。")
    print(f"目录: {cache_dir}")
    choice = input("删除? [y/N]: ").strip().lower()
    
    if choice == 'y':
        print("删除中...")
        try:
            shutil.rmtree(cache_dir)
            print("✓ 已删除")
        except Exception as e:
            print(f"✗ 删除失败: {e}")
            print("请手动删除这个目录后重试")
            sys.exit(1)
    else:
        print("跳过删除")

# 2. 下载模型
print("\n" + "="*60)
print("开始下载模型...")
print("="*60)
print("⚠ 这将下载约 1.4GB 数据，请耐心等待...")
print("⚠ 不要中断程序，让它完整下载一次")
print("="*60 + "\n")

try:
    from marker.converters.pdf import PdfConverter
    from marker.models import create_model_dict
    
    print("初始化转换器（会触发模型下载）...")
    artifact_dict = create_model_dict()
    converter = PdfConverter(artifact_dict=artifact_dict)
    
    print("\n" + "="*60)
    print("✅ 模型下载完成！")
    print("="*60)
    
    # 验证
    cache_dir = Path.home() / "AppData/Local/datalab/datalab/Cache/models/layout/2025_09_23"
    if cache_dir.exists():
        model_file = cache_dir / "model.safetensors"
        if model_file.exists():
            size = model_file.stat().st_size / (1024**3)  # GB
            print(f"模型文件: {model_file}")
            print(f"大小: {size:.2f} GB")
            
            if size > 1.0:
                print("\n✅ 模型完整，可以使用了！")
                sys.exit(0)
            else:
                print(f"\n⚠ 模型文件太小（{size:.2f} GB < 1 GB），可能下载不完整")
                sys.exit(1)
    
    print("\n⚠ 未找到模型文件，下载可能失败")
    sys.exit(1)
    
except KeyboardInterrupt:
    print("\n\n⚠ 下载被中断")
    print("请重新运行此脚本，并让它完整下载")
    sys.exit(1)
    
except Exception as e:
    print(f"\n✗ 下载失败: {e}")
    print("\n可能的原因：")
    print("1. 网络连接问题")
    print("2. HuggingFace 访问受限")
    print("3. 磁盘空间不足")
    print("\n建议：")
    print("1. 检查网络连接")
    print("2. 尝试使用 VPN 或代理")
    print("3. 确保有足够磁盘空间（至少 2GB）")
    sys.exit(1)
