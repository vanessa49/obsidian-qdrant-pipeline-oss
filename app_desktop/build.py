"""
打包脚本 - 生成独立 exe（包含内置知识库）
使用 PyInstaller 打包桌面应用
"""

import os
import shutil
import subprocess
from pathlib import Path
from datetime import datetime

import yaml


SENSITIVE_CONFIG_KEYS = {
    "api_key",
    "apikey",
    "token",
    "access_token",
    "secret",
    "client_secret",
    "password",
    "private_key",
}


def _secret_config_fields(value, prefix=""):
    """Return paths to non-empty secret-like YAML fields without their values."""
    fields = []
    if isinstance(value, dict):
        for key, child in value.items():
            key_text = str(key)
            child_prefix = f"{prefix}.{key_text}" if prefix else key_text
            normalized_key = key_text.lower()
            is_sensitive = (
                normalized_key in SENSITIVE_CONFIG_KEYS
                or normalized_key.endswith(("_api_key", "_token", "_secret", "_password"))
            )
            if is_sensitive and isinstance(child, str) and child.strip():
                fields.append(child_prefix)
            else:
                fields.extend(_secret_config_fields(child, child_prefix))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            fields.extend(_secret_config_fields(child, f"{prefix}[{index}]"))
    return fields


def refuse_secret_bearing_local_config():
    """Fail closed rather than allowing a reusable local credential into a build."""
    config_path = Path("config_local.yaml")
    if not config_path.exists():
        return

    try:
        config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise RuntimeError("config_local.yaml cannot be parsed safely") from exc

    secret_fields = _secret_config_fields(config)
    if secret_fields:
        field_list = ", ".join(secret_fields)
        raise RuntimeError(
            "Refusing to package config_local.yaml because it contains a secret-like "
            f"field ({field_list}). Remove the value and provide credentials at runtime "
            "through environment variables instead."
        )


def prepare_bundled_kb():
    """准备内置知识库包"""
    print("\n" + "="*60)
    print("步骤 1: 准备内置知识库")
    print("="*60)
    
    from kb_manager import create_bundled_kb
    from qdrant_client import QdrantClient
    
    source_path = "../qdrant_data"
    
    # 检查源数据是否存在
    if not Path(source_path).exists():
        print(f"✗ 源 Qdrant 数据不存在: {source_path}")
        print("  请先运行 migrate.py 或 ingest.py 生成知识库数据")
        return False
    
    # 统计文档数量
    try:
        client = QdrantClient(path=source_path)
        collection_info = client.get_collection("personal_kb")
        doc_count = collection_info.points_count
        print(f"  检测到 {doc_count} 个向量点")
    except Exception as e:
        print(f"  ⚠ 无法统计文档数量: {e}")
        doc_count = "unknown"
    
    # 创建元数据
    metadata = {
        "version": "1.0",
        "document_count": doc_count,
        "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "description": "用研知识库快照"
    }
    
    # 创建内置知识库包
    success = create_bundled_kb(source_path, "bundled_kb", metadata)
    
    if success:
        # 计算大小
        bundled_size = sum(
            f.stat().st_size 
            for f in Path("bundled_kb").rglob("*") 
            if f.is_file()
        ) / (1024 * 1024)  # MB
        
        print(f"  内置知识库大小: {bundled_size:.1f} MB")
    
    return success


def clean_build():
    """清理之前的构建文件"""
    print("\n" + "="*60)
    print("步骤 2: 清理构建文件")
    print("="*60)
    
    dirs_to_remove = ["build", "dist", "__pycache__"]
    files_to_remove = ["*.spec"]
    
    for dir_name in dirs_to_remove:
        if Path(dir_name).exists():
            shutil.rmtree(dir_name)
            print(f"  ✓ 删除 {dir_name}/")
    
    for pattern in files_to_remove:
        for file in Path(".").glob(pattern):
            file.unlink()
            print(f"  ✓ 删除 {file}")


def build_exe():
    """构建 exe"""
    print("\n" + "="*60)
    print("步骤 3: 打包 exe")
    print("="*60)
    
    # 检查 Ollama 是否已准备
    ollama_path = Path("bundled_ollama")
    if not ollama_path.exists():
        print("\n⚠️  警告: bundled_ollama 目录不存在")
        print("   如果需要内置 Ollama，请先复制文件：")
        print("   1. mkdir bundled_ollama\\bin")
        print("   2. mkdir bundled_ollama\\models")
        print("   3. copy ollama.exe bundled_ollama\\bin\\")
        print("   4. xcopy /E /I .ollama\\models bundled_ollama\\models")
        print("\n   继续打包（不包含 Ollama）...")
    else:
        # 计算 Ollama 大小
        ollama_size = sum(
            f.stat().st_size 
            for f in ollama_path.rglob("*") 
            if f.is_file()
        ) / (1024 * 1024)  # MB
        print(f"  ✓ 检测到 Ollama 文件: {ollama_size:.1f} MB")
    
    # PyInstaller 命令
    cmd = [
        "pyinstaller",
        #"--onefile",                           # 单文件模式
        #"--windowed",                          # 无控制台窗口（调试时注释掉）
        "--name=KnowledgeAssistant",           # exe 名称
        "--add-data=config.example.yaml;.",    # Public template only; never a local config
        "--add-data=bundled_kb;bundled_kb",    # 包含内置知识库（关键！）
        "--hidden-import=gradio",
        "--hidden-import=yaml",
        "--hidden-import=requests",
        "--hidden-import=qdrant_client",
        "--hidden-import=groovy",              # 显式导入 groovy
        "--collect-all=gradio",                # 收集 gradio 所有资源
        "--collect-all=groovy",                # 收集 groovy 所有资源（包括 version.txt）
        "--collect-all=safehttpx",
        "--collect-data=safehttpx",
        "launcher.py"                          # 入口文件
    ]
    
    # 如果 Ollama 存在，添加到打包
    if ollama_path.exists():
        cmd.insert(-1, "--add-data=bundled_ollama;bundled_ollama")
        print("  ✓ 将打包 Ollama 到应用中")
    
    print("  执行打包命令...")
    print(f"  {' '.join(cmd)}")
    
    # 执行打包
    result = subprocess.run(cmd, text=True)
    
    if result.returncode == 0:
        print("\n✓ 打包成功！")
        
        # 计算 exe 大小
        exe_path = Path("dist/KnowledgeAssistant.exe")
        if exe_path.exists():
            exe_size = exe_path.stat().st_size / (1024 * 1024)  # MB
            print(f"  exe 大小: {exe_size:.1f} MB")
        
        return True
    else:
        print("\n✗ 打包失败")
        print(result.stderr)
        return False


def copy_resources():
    """复制必要的资源文件到 dist 目录"""
    print("\n" + "="*60)
    print("步骤 4: 复制资源文件")
    print("="*60)
    
    dist_dir = Path("dist/KnowledgeAssistant")
    if not dist_dir.exists():
        print("  ✗ dist/KnowledgeAssistant 目录不存在")
        return
    
    # 创建用户指南
    readme_content = """# 公司知识库助手

## 使用方法

1. 双击 KnowledgeAssistant.exe
2. 等待浏览器自动打开（首次启动需要 10-15 秒）
3. 在问答界面输入问题
4. 获得基于公司知识库的回答

## 重要提示

⚠️ 请保持整个文件夹完整，不要只复制 exe 文件！
   必须包含：
   - KnowledgeAssistant.exe
   - _internal/ 文件夹（包含所有依赖）

## 注意事项

- 需要网络连接（访问云端 AI 服务）
- 首次启动会自动初始化知识库
- 所有数据仅在本地处理，不会上传

## 常见问题

**Q: 双击没反应？**
A: 右键 → 以管理员身份运行

**Q: 浏览器没打开？**
A: 手动访问 http://127.0.0.1:7860

**Q: 提示找不到文件？**
A: 确保 _internal 文件夹和 exe 在同一目录

## 获取帮助

遇到问题请联系 IT 支持或管理员。
"""
    
    (dist_dir / "README.txt").write_text(readme_content, encoding="utf-8")
    print("  ✓ README.txt")


def main():
    """主函数"""
    print("="*60)
    print("桌面应用打包工具（内置知识库版本）")
    print("="*60)
    
    # 检查是否在正确的目录
    if not Path("launcher.py").exists():
        print("✗ 错误: 请在 app_desktop 目录下运行此脚本")
        return

    try:
        refuse_secret_bearing_local_config()
    except RuntimeError as exc:
        print(f"✗ Refusing desktop build: {exc}")
        return
    
    # 步骤 1: 准备内置知识库
    if not prepare_bundled_kb():
        print("\n✗ 内置知识库准备失败，终止打包")
        return
    
    # 步骤 2: 清理
    clean_build()
    
    # 步骤 3: 打包
    if not build_exe():
        print("\n✗ 打包失败")
        return
    
    # 步骤 4: 复制资源
    copy_resources()
    
    print("\n" + "="*60)
    print("打包完成！")
    print("="*60)
    print("\n交付文件:")
    print("  📦 dist/KnowledgeAssistant/")
    print("     ├── KnowledgeAssistant.exe")
    print("     ├── _internal/ (依赖文件)")
    print("     └── README.txt")
    print("\n使用方式:")
    print("  1. 将整个 KnowledgeAssistant 文件夹发送给用户")
    print("  2. 用户双击 KnowledgeAssistant.exe")
    print("  3. 无需任何配置或安装")
    print("\n⚠️  重要提示:")
    print("  - 必须保持 exe 和 _internal 文件夹在一起")
    print("  - 不要只发送 exe 文件")
    print("\n注意事项:")
    print("  - 应用已包含完整知识库")
    print("  - 首次启动会自动初始化（10-15秒）")
    print("  - 需要网络连接访问 NVIDIA API")
    print("  - 无需 Ollama 或其他本地服务")


if __name__ == "__main__":
    main()
