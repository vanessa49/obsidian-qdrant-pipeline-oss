"""
Ollama 管理器 - 自动启动和管理内置的 Ollama 服务
"""

import os
import subprocess
import time
import requests
from pathlib import Path
import sys


class OllamaManager:
    """Ollama 服务管理器"""
    
    def __init__(self, ollama_path: str = "bundled_ollama", port: int = 11434):
        """
        初始化 Ollama 管理器
        
        Args:
            ollama_path: Ollama 安装路径
            port: Ollama 服务端口
        """
        # 尝试多个可能的位置
        possible_paths = [
            Path(ollama_path),
            Path("_internal") / ollama_path,
        ]
        
        self.ollama_path = None
        for path in possible_paths:
            if path.exists():
                self.ollama_path = path
                break
        
        if self.ollama_path is None:
            self.ollama_path = Path(ollama_path)
        
        self.ollama_bin = self.ollama_path / "bin" / "ollama.exe"
        self.models_path = self.ollama_path / "models"
        self.port = port
        self.process = None
        
    def is_installed(self) -> bool:
        """检查 Ollama 是否已安装"""
        return self.ollama_bin.exists()
    
    def is_running(self) -> bool:
        """检查 Ollama 服务是否正在运行"""
        try:
            response = requests.get(f"http://localhost:{self.port}/api/tags", timeout=2)
            return response.status_code == 200
        except:
            return False
    
    def start(self) -> bool:
        """
        启动 Ollama 服务
        
        Returns:
            是否成功启动
        """
        if self.is_running():
            print("✓ Ollama 服务已在运行")
            return True
        
        if not self.is_installed():
            print(f"✗ Ollama 未找到: {self.ollama_bin}")
            return False
        
        print("正在启动 Ollama 服务...")
        
        try:
            # 设置环境变量
            env = os.environ.copy()
            env["OLLAMA_MODELS"] = str(self.models_path.absolute())
            env["OLLAMA_HOST"] = f"127.0.0.1:{self.port}"
            
            # 启动 Ollama 服务（后台运行）
            self.process = subprocess.Popen(
                [str(self.ollama_bin), "serve"],
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            )
            
            # 等待服务启动
            for i in range(30):  # 最多等待 30 秒
                time.sleep(1)
                if self.is_running():
                    print(f"✓ Ollama 服务启动成功 (端口: {self.port})")
                    return True
            
            print("✗ Ollama 服务启动超时")
            return False
            
        except Exception as e:
            print(f"✗ Ollama 服务启动失败: {e}")
            return False
    
    def stop(self):
        """停止 Ollama 服务"""
        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=5)
                print("✓ Ollama 服务已停止")
            except:
                self.process.kill()
    
    def check_model(self, model_name: str = "bge-m3") -> bool:
        """
        检查模型是否可用
        
        Args:
            model_name: 模型名称
            
        Returns:
            模型是否可用
        """
        if not self.is_running():
            return False
        
        try:
            response = requests.get(f"http://localhost:{self.port}/api/tags", timeout=5)
            if response.status_code == 200:
                models = response.json().get("models", [])
                for model in models:
                    if model_name in model.get("name", ""):
                        return True
            return False
        except:
            return False
    
    def ensure_running(self) -> bool:
        """
        确保 Ollama 服务正在运行
        
        Returns:
            是否成功
        """
        if self.is_running():
            return True
        
        return self.start()


if __name__ == "__main__":
    # 测试
    manager = OllamaManager()
    
    print("="*60)
    print("Ollama 管理器测试")
    print("="*60)
    
    print(f"\nOllama 路径: {manager.ollama_path}")
    print(f"Ollama 可执行文件: {manager.ollama_bin}")
    print(f"模型路径: {manager.models_path}")
    
    print(f"\n已安装: {manager.is_installed()}")
    print(f"正在运行: {manager.is_running()}")
    
    if manager.is_installed():
        print("\n尝试启动...")
        if manager.ensure_running():
            print("✓ 服务运行中")
            
            print("\n检查 bge-m3 模型...")
            if manager.check_model("bge-m3"):
                print("✓ bge-m3 模型可用")
            else:
                print("✗ bge-m3 模型不可用")
