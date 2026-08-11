"""
Ollama 文件准备脚本
帮助用户将本地 Ollama 复制到项目中
"""

import os
import shutil
import subprocess
from pathlib import Path


def find_ollama():
    """查找 Ollama 安装位置"""
    print("正在查找 Ollama...")
    
    try:
        result = subprocess.run(
            ["where", "ollama"],
            capture_output=True,
            text=True,
            shell=True
        )
        
        if result.returncode == 0:
            ollama_path = result.stdout.strip().split('\n')[0]
            print(f"✓ 找到 Ollama: {ollama_path}")
            return Path(ollama_path)
        else:
            print("✗ 未找到 Ollama")
            return None
            
    except Exception as e:
        print(f"✗ 查找失败: {e}")
        return None


def find_models():
    """查找模型文件夹"""
    print("\n正在查找模型文件...")
    
    # 常见位置
    user_home = Path.home()
    possible_paths = [
        user_home / ".ollama" / "models",
        Path(os.environ.get("OLLAMA_MODELS", "")),
    ]
    
    for path in possible_paths:
        if path.exists() and path.is_dir():
            # 检查是否有 bge-m3
            has_bge = False
            for item in path.rglob("*"):
                if "bge" in item.name.lower():
                    has_bge = True
                    break
            
            if has_bge:
                print(f"✓ 找到模型文件夹: {path}")
                print(f"  包含 bge-m3 模型")
                return path
            else:
                print(f"⚠ 找到模型文件夹但未检测到 bge-m3: {path}")
    
    print("✗ 未找到模型文件夹")
    return None


def copy_ollama_files(ollama_exe, models_dir):
    """复制 Ollama 文件到项目"""
    print("\n开始复制文件...")
    
    # 创建目标目录
    target_dir = Path("bundled_ollama")
    target_bin = target_dir / "bin"
    target_models = target_dir / "models"
    
    # 清理旧文件
    if target_dir.exists():
        print("  清理旧文件...")
        shutil.rmtree(target_dir)
    
    # 创建目录
    target_bin.mkdir(parents=True, exist_ok=True)
    target_models.mkdir(parents=True, exist_ok=True)
    
    # 复制 exe
    print(f"  复制 ollama.exe...")
    shutil.copy2(ollama_exe, target_bin / "ollama.exe")
    
    # 复制模型
    print(f"  复制模型文件（可能需要几分钟）...")
    shutil.copytree(models_dir, target_models, dirs_exist_ok=True)
    
    # 计算大小
    total_size = sum(
        f.stat().st_size 
        for f in target_dir.rglob("*") 
        if f.is_file()
    ) / (1024 * 1024)  # MB
    
    print(f"\n✓ 复制完成！")
    print(f"  总大小: {total_size:.1f} MB")
    print(f"  位置: {target_dir.absolute()}")
    
    return True


def main():
    """主函数"""
    print("="*60)
    print("Ollama 文件准备工具")
    print("="*60)
    print("\n此工具将帮助你将本地 Ollama 复制到项目中")
    print("以便打包成独立的 exe 应用\n")
    
    # 检查当前目录
    if not Path("launcher.py").exists():
        print("✗ 错误: 请在 app_desktop 目录下运行此脚本")
        input("\n按回车键退出...")
        return
    
    # 查找 Ollama
    ollama_exe = find_ollama()
    if not ollama_exe:
        print("\n请确保已安装 Ollama:")
        print("  下载地址: https://ollama.com/download")
        input("\n按回车键退出...")
        return
    
    # 查找模型
    models_dir = find_models()
    if not models_dir:
        print("\n请确保已下载 bge-m3 模型:")
        print("  运行命令: ollama pull bge-m3")
        input("\n按回车键退出...")
        return
    
    # 确认
    print("\n" + "="*60)
    print("准备复制以下文件:")
    print("="*60)
    print(f"  Ollama: {ollama_exe}")
    print(f"  模型: {models_dir}")
    print(f"  目标: bundled_ollama/")
    
    confirm = input("\n是否继续? (y/n): ")
    if confirm.lower() != 'y':
        print("已取消")
        return
    
    # 复制文件
    if copy_ollama_files(ollama_exe, models_dir):
        print("\n" + "="*60)
        print("准备完成！")
        print("="*60)
        print("\n下一步:")
        print("  1. 运行 python build.py 打包应用")
        print("  2. Ollama 将自动包含在 exe 中")
        print("  3. 用户无需安装 Ollama 即可使用")
    
    input("\n按回车键退出...")


if __name__ == "__main__":
    main()
