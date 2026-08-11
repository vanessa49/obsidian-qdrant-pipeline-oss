"""
桌面知识库助手 - Gradio UI
极简界面：问题输入 → 回答 + 来源
"""

import gradio as gr
import yaml
from pathlib import Path
from rag_engine import RAGEngine


def load_ui_config():
    """加载 UI 配置"""
    config_path = Path(__file__).parent / "config_local.yaml"
    with open(config_path, encoding="utf-8") as f:
        config = yaml.safe_load(f)
    return config["ui"]


def format_sources(sources):
    """格式化来源信息为 Markdown"""
    if not sources:
        return "*没有找到相关来源*"
    
    lines = ["### 📚 参考来源\n"]
    for i, src in enumerate(sources, 1):
        lines.append(f"**{i}.** `{src['file']}` #chunk_{src['chunk_index']} (相似度: {src['score']})")
        #lines.append(f"> {src['preview']}\n")
    
    return "\n".join(lines)


def format_metadata(model, retrieval_count):
    """格式化元数据"""
    return f"*使用模型: {model} | 检索到 {retrieval_count} 条相关内容*"


class KnowledgeAssistant:
    """知识库助手应用"""
    
    def __init__(self):
        """初始化应用"""
        self.ui_config = load_ui_config()
        
        # 初始化 RAG 引擎
        print("正在初始化知识库助手...")
        try:
            self.engine = RAGEngine()
            self.ready = True
            print("✓ 初始化成功")
        except Exception as e:
            print(f"✗ 初始化失败: {e}")
            self.ready = False
            self.error_message = str(e)
    
    def ask(self, question, history):
        """
        处理用户问题
        
        Args:
            question: 用户问题
            history: 对话历史（Gradio ChatInterface 格式）
            
        Returns:
            回答内容（会自动添加到 history）
        """
        if not self.ready:
            return f"❌ 系统未就绪: {self.error_message}"
        
        if not question or not question.strip():
            return "请输入问题"
        
        try:
            # 调用 RAG 引擎
            result = self.engine.ask(question.strip())
            
            # 格式化回答
            answer_parts = [
                "### 💡 回答\n",
                result["answer"],
                "\n\n---\n",
                format_sources(result["sources"]),
                "\n\n---\n",
                format_metadata(result["model"], result["retrieval_count"])
            ]
            
            return "".join(answer_parts)
            
        except Exception as e:
            return f"❌ 查询失败: {str(e)}"
    
    def launch(self):
        """启动 Gradio 界面"""
        if not self.ready:
            # 如果初始化失败，显示错误界面
            with gr.Blocks(title="知识库助手 - 错误") as demo:
                gr.Markdown(f"# ❌ 初始化失败\n\n{self.error_message}")
            
            demo.launch(
                server_name=self.ui_config["server_name"],
                server_port=self.ui_config["server_port"],
                share=False,
                inbrowser=False
            )
            return
        
        # 创建 Gradio 界面
        with gr.Blocks(title=self.ui_config["title"]) as demo:
            
            gr.Markdown(f"# {self.ui_config['title']}")
            gr.Markdown(self.ui_config["description"])
            
            # 使用 ChatInterface 组件（简化版，兼容 Gradio 6.0）
            chat = gr.ChatInterface(
                fn=self.ask,
                textbox=gr.Textbox(
                    placeholder="输入你的问题...",
                    container=False
                ),
                examples=[
                    "银发群体的审美偏好是怎么样",
                    "用户对Z11的外观态度是怎么样的呢"
                ]
            )
            
            gr.Markdown("""
---
### 💡 使用提示
- 输入问题后点击"提问"按钮
- 系统会从本地知识库检索相关内容并生成回答
- 如果知识库中没有相关内容，系统会明确告知

### ⚙️ 系统信息
- 知识库: Qdrant (personal_kb)
- Embedding 模型: NVIDIA API (baai/bge-m3)
- 生成模型: NVIDIA API (多模型回退)
- **完全云端运行，无需本地安装任何服务**
            """)
        
        # 启动应用
        demo.launch(
            server_name=self.ui_config["server_name"],
            server_port=self.ui_config["server_port"],
            share=self.ui_config["share"],
            inbrowser=self.ui_config["auto_launch"]
        )


def main():
    """主函数"""
    app = KnowledgeAssistant()
    app.launch()


if __name__ == "__main__":
    main()
