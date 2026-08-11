"""
环境检查脚本 - 验证所有依赖和服务是否正常
"""

import sys
from pathlib import Path

import requests


def check_python_version():
    """检查 Python 版本"""
    print("检查 Python 版本...")
    version = sys.version_info
    if version.major >= 3 and version.minor >= 8:
        print(f"  ✓ Python {version.major}.{version.minor}.{version.micro}")
        return True
    else:
        print(f"  ✗ Python 版本过低: {version.major}.{version.minor}.{version.micro}")
        print(f"    需要 Python 3.8+")
        return False


def check_package(package_name, import_name=None):
    """检查 Python 包是否安装"""
    if import_name is None:
        import_name = package_name
    
    try:
        __import__(import_name)
        print(f"  ✓ {package_name}")
        return True
    except ImportError:
        print(f"  ✗ {package_name} 未安装")
        return False


def check_python_packages():
    """检查所有 Python 包"""
    print("\n检查 Python 包...")
    
    packages = [
        ("markitdown", "markitdown"),
        ("pymupdf4llm", "pymupdf4llm"),
        ("qdrant-client", "qdrant_client"),
        ("watchdog", "watchdog"),
        ("pyyaml", "yaml"),
        ("requests", "requests"),
        ("marker-pdf", "marker"),
        ("python-pptx", "pptx"),
        ("Pillow", "PIL"),
        ("pymupdf", "fitz"),
    ]
    
    results = []
    for package_name, import_name in packages:
        results.append(check_package(package_name, import_name))
    
    return all(results)


def check_ollama():
    """检查 Ollama 服务"""
    print("\n检查 Ollama 服务...")
    
    try:
        response = requests.get("http://localhost:11434/api/tags", timeout=5)
        response.raise_for_status()
        
        data = response.json()
        models = data.get("models", [])
        model_names = [m.get("name", "") for m in models]
        
        print(f"  ✓ Ollama 服务运行正常")
        print(f"    已安装模型: {len(models)} 个")
        
        # 检查必需的模型
        required_models = ["bge-m3", "qwen2.5:7b"]
        missing_models = []
        
        for required in required_models:
            found = any(required in name for name in model_names)
            if found:
                print(f"    ✓ {required}")
            else:
                print(f"    ✗ {required} 未安装")
                missing_models.append(required)
        
        if missing_models:
            print(f"\n  请安装缺失的模型:")
            for model in missing_models:
                print(f"    ollama pull {model}")
            return False
        
        return True
        
    except requests.exceptions.ConnectionError:
        print(f"  ✗ 无法连接到 Ollama (http://localhost:11434)")
        print(f"    请确保 Ollama 服务正在运行")
        return False
    except Exception as e:
        print(f"  ✗ Ollama 检查失败: {e}")
        return False


def check_qdrant():
    """检查 Qdrant 服务"""
    print("\n检查 Qdrant 服务...")

    # 读取配置，判断是本地路径模式还是 URL 模式
    cfg_path = Path("config.yaml")
    qdrant_config = {"url": "http://127.0.0.1:6333"}  # 默认
    if cfg_path.exists():
        import yaml
        with open(cfg_path, encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
        qdrant_config = cfg.get("qdrant", qdrant_config)

    # 本地路径模式：直接检查目录是否可写，不发 HTTP 请求
    if "path" in qdrant_config:
        local_path = Path(qdrant_config["path"])
        try:
            local_path.mkdir(parents=True, exist_ok=True)
            print(f"  ✓ Qdrant 本地模式，数据目录: {local_path.resolve()}")
            return True
        except Exception as e:
            print(f"  ✗ Qdrant 本地目录无法创建: {e}")
            return False

    # URL 模式：发 HTTP 请求
    qdrant_url = qdrant_config.get("url", "http://127.0.0.1:6333")
    try:
        response = requests.get(f"{qdrant_url}/collections", timeout=5)
        response.raise_for_status()
        
        data = response.json()
        collections = data.get("result", {}).get("collections", [])
        
        print(f"  ✓ Qdrant 服务运行正常 ({qdrant_url})")
        print(f"    已有 collections: {len(collections)} 个")
        
        has_kb = any(c.get("name") == "personal_kb" for c in collections)
        if has_kb:
            print(f"    ✓ personal_kb collection 已存在")
        else:
            print(f"    ⊘ personal_kb collection 不存在（首次运行时会自动创建）")
        
        return True
        
    except requests.exceptions.ConnectionError:
        print(f"  ✗ 无法连接到 Qdrant ({qdrant_url})")
        print(f"    请检查 NAS 是否在线，以及 Qdrant 服务是否运行")
        return False
    except Exception as e:
        print(f"  ✗ Qdrant 检查失败: {e}")
        return False


def check_vision_api():
    """检查 Vision API"""
    print("\n检查 Pollinations Vision API...")
    
    try:
        # 简单的健康检查（不发送实际请求）
        response = requests.get("https://text.pollinations.ai/", timeout=10)
        
        if response.status_code in [200, 405]:  # 405 是因为不支持 GET
            print(f"  ✓ Vision API 可访问")
            return True
        else:
            print(f"  ⊘ Vision API 返回状态码: {response.status_code}")
            print(f"    可能可用，但需要实际测试")
            return True
            
    except requests.exceptions.ConnectionError:
        print(f"  ✗ 无法连接到 Vision API")
        print(f"    请检查网络连接")
        return False
    except Exception as e:
        print(f"  ⊘ Vision API 检查失败: {e}")
        print(f"    可能可用，但需要实际测试")
        return True


def check_paths():
    """检查路径配置"""
    print("\n检查路径配置...")
    
    # 这里只是示例，实际路径需要用户配置
    print("  ⊘ 请确保以下路径已配置:")
    print("    - Obsidian vault 路径 (例如: <VAULT_PATH>)")
    print("    - 监控文件夹路径 (例如: <INBOX_PATH>)")
    print("\n  使用 --vault 和 --watch 参数指定路径")
    
    return True


def main():
    """主函数"""
    print("="*60)
    print("个人知识库自动化入库管道 - 环境检查")
    print("="*60)
    
    results = []
    
    # 检查 Python 版本
    results.append(check_python_version())
    
    # 检查 Python 包
    results.append(check_python_packages())
    
    # 检查 Ollama
    results.append(check_ollama())
    
    # 检查 Qdrant
    results.append(check_qdrant())
    
    # 检查 Vision API
    results.append(check_vision_api())
    
    # 检查路径
    results.append(check_paths())
    
    # 总结
    print("\n" + "="*60)
    if all(results):
        print("✓ 所有检查通过！环境配置正常")
        print("\n下一步:")
        print("  python ingest.py --file test.txt --vault <VAULT_PATH>")
    else:
        print("✗ 部分检查失败，请根据上述提示修复")
        print("\n常见问题:")
        print("  1. Python 包缺失: pip install -r requirements.txt")
        print("  2. Ollama 模型缺失: ollama pull bge-m3 && ollama pull qwen2.5:7b")
        print("  3. 服务未运行: 启动 Ollama 和 Qdrant")
    print("="*60)


if __name__ == "__main__":
    main()
