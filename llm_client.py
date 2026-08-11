"""
LLM 客户端模块 - 统一的 LLM 调用接口
支持多提供商回退策略：NVIDIA API → Ollama 本地
"""

import base64
import io
import os
from typing import Optional

import requests
import yaml
from PIL import Image


# 全局配置缓存
_config = None


def _load_config():
    """加载配置文件（支持配置合并）"""
    global _config
    if _config is None:
        # 基础配置
        base_config = {
            "llm": {
                "provider": "nvidia",
                "nvidia": {
                    "api_key": "",
                    "base_url": "https://integrate.api.nvidia.com/v1",
                    "models": ["qwen/qwen2.5-72b-instruct"],
                    "timeout": 60,
                    "temperature": 0.3,
                    "max_tokens": 1024
                }
            }
        }
        
        # 尝试加载主配置
        try:
            with open("config.yaml", "r", encoding="utf-8") as f:
                main_config = yaml.safe_load(f)
                # 合并配置：基础配置 + 主配置
                _merge_configs(base_config, main_config)
        except FileNotFoundError:
            pass  # 主配置不存在，使用基础配置
        
        # 尝试加载桌面应用配置
        try:
            with open("app_desktop/config_local.yaml", "r", encoding="utf-8") as f:
                desktop_config = yaml.safe_load(f)
                # 合并配置：基础配置 + 桌面配置
                _merge_configs(base_config, desktop_config)
        except FileNotFoundError:
            pass  # 桌面配置不存在

        # A process environment credential is preferred over an ignored local
        # configuration file so a shared checkout never needs a reusable key.
        environment_api_key = os.environ.get("NVIDIA_API_KEY")
        if environment_api_key:
            base_config["llm"]["nvidia"]["api_key"] = environment_api_key
        
        _config = base_config
    
    return _config


def _merge_configs(base, new):
    """递归合并两个配置字典（新配置覆盖基础配置）"""
    for key, value in new.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            _merge_configs(base[key], value)
        else:
            base[key] = value


def call_llm(prompt: str, system: str = "", mode: str = "text") -> str:
    """
    调用 LLM 生成文本
    
    策略：先尝试 NVIDIA API，失败后回退到本地 Ollama
    
    Args:
        prompt: 用户提示词
        system: 系统提示词（可选）
        mode: 模式，目前仅支持 "text"
        
    Returns:
        LLM 生成的文本内容
        
    Raises:
        RuntimeError: 所有 LLM 提供商均失败时抛出
    """
    config = _load_config()
    llm_config = config.get("llm", {})
    provider = llm_config.get("provider", "nvidia")
    
    # 第一优先：NVIDIA API
    if provider == "nvidia":
        nvidia_config = llm_config.get("nvidia", {})
        api_key = nvidia_config.get("api_key", "")
        base_url = nvidia_config.get("base_url", "https://integrate.api.nvidia.com/v1")
        models = nvidia_config.get("models", [
            "qwen/qwen3.5-122b-a10b",
            "deepseek-ai/deepseek-v4-pro",
            "meta/llama-3.3-70b-instruct"
        ])
        timeout = nvidia_config.get("timeout", 60)
        temperature = nvidia_config.get("temperature", 0.3)
        max_tokens = nvidia_config.get("max_tokens", 1024)
        
        if api_key:
            print(f"  → 尝试 NVIDIA API (模型: {len(models)}个)")
            # 尝试配置中的所有模型
            for model in models:
                try:
                    messages = []
                    if system:
                        messages.append({"role": "system", "content": system})
                    messages.append({"role": "user", "content": prompt})
                    
                    response = requests.post(
                        f"{base_url}/chat/completions",
                        headers={
                            "Authorization": f"Bearer {api_key}",
                            "Content-Type": "application/json"
                        },
                        json={
                            "model": model,
                            "messages": messages,
                            "temperature": temperature,
                            "max_tokens": max_tokens
                        },
                        timeout=timeout
                    )
                    
                    response.raise_for_status()
                    result = response.json()
                    content = result["choices"][0]["message"]["content"]
                    
                    if content:
                        return content
                    
                except Exception as e:
                    print(f"  ✗ NVIDIA 模型 {model} 失败: {e}")
                    continue
            
            print("  ✗ 所有 NVIDIA 模型均失败，切换到本地 Ollama...")
        else:
            print("  ✗ NVIDIA API key 未配置，切换到本地 Ollama...")
    
    # 第二优先：本地 Ollama
    try:
        ollama_url = "http://localhost:11434/api/generate"
        
        # 尝试从配置中获取 Ollama 模型，如果没有则使用默认
        ollama_config = config.get("ollama", {})
        ollama_model = ollama_config.get("llm_model", "qwen2.5:7b")
        
        print(f"  → 尝试本地 Ollama (模型: {ollama_model})")
        
        response = requests.post(
            ollama_url,
            json={
                "model": ollama_model,
                "prompt": prompt,
                "system": system,
                "stream": False,
                "options": {
                    "temperature": 0.3,
                    "top_p": 0.9
                }
            },
            timeout=120
        )
        
        response.raise_for_status()
        result = response.json()
        content = result.get("response", "").strip()
        
        if content:
            return content
        else:
            raise ValueError("Ollama 返回空内容")
    
    except Exception as e:
        raise RuntimeError(f"所有 LLM 提供商均失败。错误详情: {e}")


def call_vision(image_base64: str, prompt: str) -> str:
    """
    调用视觉模型分析图片
    
    策略：
    1. 先尝试 Pollinations（免费，多模型回退）
    2. 失败后尝试 NVIDIA Vision 模型
    
    Args:
        image_base64: Base64 编码的图片
        prompt: 分析提示词
        
    Returns:
        模型生成的图片分析结果
        
    Raises:
        RuntimeError: 所有视觉模型均失败时抛出
    """
    config = _load_config()
    
    # 第一优先：Pollinations（从配置读取模型列表）
    vision_config = config.get("vision_api", {})
    pollinations_models = vision_config.get("models", [
        "openai", "gemini", "openai-large", "llama-vision"
    ])
    
    for model in pollinations_models:
        try:
            result = _call_pollinations_vision(image_base64, prompt, model)
            
            # 检查是否成功（不包含失败标记）
            if not result.startswith("[图片页，提取失败"):
                return result
        
        except Exception as e:
            print(f"  ✗ {model} failed: {e}")
            continue
    
    print("  ✗ Pollinations 所有模型均失败，切换到 NVIDIA Vision...")
    
    # 第二优先：NVIDIA Vision 模型
    config = _load_config()
    llm_config = config.get("llm", {})
    
    if llm_config.get("provider") == "nvidia":
        nvidia_config = llm_config.get("nvidia", {})
        api_key = nvidia_config.get("api_key", "")
        base_url = nvidia_config.get("base_url", "https://integrate.api.nvidia.com/v1")
        
        if api_key:
            # NVIDIA 视觉模型列表
            vision_models = [
                "meta/llama-4-maverick-17b-128e-instruct",
                "meta/llama-3.2-90b-vision-instruct",
                "mistralai/mistral-large-3-675b-instruct-2512"
            ]
            
            for model in vision_models:
                try:
                    response = requests.post(
                        f"{base_url}/chat/completions",
                        headers={
                            "Authorization": f"Bearer {api_key}",
                            "Content-Type": "application/json"
                        },
                        json={
                            "model": model,
                            "messages": [{
                                "role": "user",
                                "content": [
                                    {
                                        "type": "image_url",
                                        "image_url": {
                                            "url": f"data:image/jpeg;base64,{image_base64}"
                                        }
                                    },
                                    {
                                        "type": "text",
                                        "text": prompt
                                    }
                                ]
                            }],
                            "max_tokens": 1024,
                            "temperature": 0.3
                        },
                        timeout=60
                    )
                    
                    response.raise_for_status()
                    result = response.json()
                    content = result["choices"][0]["message"]["content"]
                    
                    if content:
                        return content
                
                except Exception as e:
                    print(f"  ✗ NVIDIA Vision 模型 {model} 失败: {e}")
                    continue
    
    # 所有模型均失败
    raise RuntimeError("所有视觉模型均失败")


def _call_pollinations_vision(base64_image: str, prompt: str, model: str) -> str:
    """
    调用 Pollinations Vision API
    
    Args:
        base64_image: Base64 编码的图片
        prompt: 分析提示词
        model: 模型名称
        
    Returns:
        模型生成的分析结果
    """
    api_url = "https://text.pollinations.ai/"
    
    payload = {
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "image": f"data:image/jpeg;base64,{base64_image}"
                    },
                    {
                        "type": "text",
                        "text": prompt
                    }
                ]
            }
        ],
        "model": model,
        "jsonMode": False,
        "seed": 42
    }
    
    response = requests.post(
        api_url,
        json=payload,
        timeout=60,
        headers={"Content-Type": "application/json"}
    )
    response.raise_for_status()
    
    result_text = response.text.strip()
    
    # 检查响应质量
    if not result_text or len(result_text) < 3:
        return "[图片页，提取失败：API 返回空内容]"
    
    # 检查是否包含"无法查看"等失败模式
    cannot_view_patterns = [
        '无法查看', 'cannot view', 'cannot see', '没有成功上传',
        '无法看到', '图片没有成功加载', 'image did not load',
        'unable to see', 'unable to view', '没有成功加载',
        'not successfully uploaded', '我无法直接查看',
        'I cannot view', 'I am unable to view'
    ]
    
    if any(pattern in result_text.lower() for pattern in cannot_view_patterns):
        return "[图片页，提取失败：API 无法识别图片]"
    
    return result_text


if __name__ == "__main__":
    # 测试代码
    print("测试 1: 文本生成")
    try:
        result = call_llm(
            prompt="用一句话解释什么是深度学习",
            system="你是一个简洁的技术助手"
        )
        print(f"结果: {result}\n")
    except Exception as e:
        print(f"失败: {e}\n")
    
    print("测试 2: 视觉分析（需要提供图片）")
    print("跳过视觉测试（需要实际图片）")
