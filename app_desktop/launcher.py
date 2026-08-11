"""
桌面应用启动器 - exe 入口点
处理打包后的路径和依赖问题
"""

import sys
import os
from pathlib import Path


def setup_environment():
    """设置运行环境"""
    # 如果是 PyInstaller 打包后的环境
    if getattr(sys, 'frozen', False):
        # 获取 exe 所在目录
        application_path = Path(sys.executable).parent
    else:
        # 开发环境
        application_path = Path(__file__).parent
    
    # 添加到 Python 路径
    sys.path.insert(0, str(application_path))
    
    # 切换工作目录到 exe 所在目录
    os.chdir(application_path)
    
    return application_path


def check_dependencies():
    """检查必要的依赖"""
    missing = []
    
    try:
        import gradio
    except ImportError:
        missing.append("gradio")
    
    try:
        import yaml
    except ImportError:
        missing.append("pyyaml")
    
    try:
        import requests
    except ImportError:
        missing.append("requests")
    
    try:
        from qdrant_client import QdrantClient
    except ImportError:
        missing.append("qdrant-client")
    
    if missing:
        print(f"❌ 缺少依赖: {', '.join(missing)}")
        print(f"请运行: pip install {' '.join(missing)}")
        return False
    
    return True


def check_config():
    """检查配置文件"""
    # 尝试多个可能的位置
    possible_paths = [
        Path("config_local.yaml"),
        Path("_internal/config_local.yaml"),
    ]
    
    for config_path in possible_paths:
        if config_path.exists():
            print(f"✓ 找到配置文件: {config_path}")
            return True
    
    print("❌ 配置文件不存在: config_local.yaml")
    print(f"   当前目录: {os.getcwd()}")
    print(f"   尝试的路径: {[str(p) for p in possible_paths]}")
    # 列出当前目录文件
    print(f"   当前目录文件: {list(Path('.').iterdir())}")
    return False


def start_ollama():
    """启动内置 Ollama 服务"""
    print("\n正在检查 Ollama 服务...")
    
    try:
        from ollama_manager import OllamaManager
        
        ollama = OllamaManager()
        
        # 检查是否已安装
        if not ollama.is_installed():
            print("⚠ 未检测到内置 Ollama，将使用外部 Ollama 服务")
            return None
        
        # 启动服务
        if ollama.ensure_running():
            print("✓ Ollama 服务已就绪")
            
            # 检查模型
            if ollama.check_model("bge-m3"):
                print("✓ bge-m3 模型可用")
            else:
                print("⚠ bge-m3 模型未找到，embedding 可能失败")
            
            return ollama
        else:
            print("⚠ Ollama 启动失败，将使用外部服务")
            return None
            
    except Exception as e:
        print(f"⚠ Ollama 初始化失败: {e}")
        return None


def main():
    """主函数"""
    print("="*60)
    print("用研知识库助手 - 启动中...")
    print("="*60)
    
    # 设置环境
    app_path = setup_environment()
    print(f"✓ 应用路径: {app_path}")
    
    # 检查依赖
    if not check_dependencies():
        # 不要调用 input()，直接退出
        import time
        time.sleep(5)  # 等待 5 秒让用户看到错误
        sys.exit(1)
    print("✓ 依赖检查通过")
    
    # 检查配置
    if not check_config():
        import time
        time.sleep(5)
        sys.exit(1)
    print("✓ 配置文件存在")
    
    # 启动 Ollama（如果存在）
    ollama_manager = start_ollama()
    
    # 初始化知识库（关键步骤）
    print("\n正在初始化知识库...")
    try:
        from kb_manager import KnowledgeBaseManager
        kb_manager = KnowledgeBaseManager()
        
        if not kb_manager.ensure_initialized():
            print("✗ 知识库初始化失败")
            import time
            time.sleep(5)
            sys.exit(1)
        
        # 显示知识库信息
        info = kb_manager.get_kb_info()
        print(f"✓ 知识库版本: {info['version']}")
        print(f"✓ 文档数量: {info['document_count']}")
        print(f"✓ 最后更新: {info['last_updated']}")
        
    except Exception as e:
        print(f"✗ 知识库初始化失败: {e}")
        import traceback
        traceback.print_exc()
        import time
        time.sleep(5)
        sys.exit(1)
    
    # 启动应用
    try:
        from app import main as app_main
        print("\n正在启动 UI...\n")
        app_main()
    except KeyboardInterrupt:
        print("\n\n应用已停止")
        # 停止 Ollama
        if ollama_manager:
            ollama_manager.stop()
    except Exception as e:
        print(f"\n❌ 启动失败: {e}")
        import traceback
        traceback.print_exc()
        import time
        time.sleep(5)
        # 停止 Ollama
        if ollama_manager:
            ollama_manager.stop()
        sys.exit(1)


if __name__ == "__main__":
    main()
