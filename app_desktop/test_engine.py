"""Manual RAG smoke test for disposable synthetic data only.

Pass an explicit synthetic config with ``--config``. Do not point this helper
at a personal vault, production Qdrant collection, or real research data.
"""

import argparse

from rag_engine import RAGEngine


def test_connection(config_path):
    """测试 Qdrant 连接"""
    print("="*60)
    print("测试 1: Qdrant 连接")
    print("="*60)
    
    try:
        engine = RAGEngine(config_path)
        print("✓ RAG 引擎初始化成功")
        return engine
    except Exception as e:
        print(f"✗ 初始化失败: {e}")
        return None


def test_retrieval(engine):
    """测试检索功能"""
    print("\n" + "="*60)
    print("测试 2: 检索功能")
    print("="*60)
    
    test_queries = [
        "synthetic release validation",
        "fictional document pipeline",
        "disposable Qdrant retrieval",
    ]
    
    for query in test_queries:
        print(f"\n查询: {query}")
        try:
            chunks = engine.retrieve(query)
            print(f"  ✓ 检索到 {len(chunks)} 条结果")
            
            if chunks:
                top = chunks[0]
                print(f"  最相关: {top['source']} (score: {top['score']:.3f})")
                print(f"  预览: {top['text'][:80]}...")
        except Exception as e:
            print(f"  ✗ 检索失败: {e}")


def test_full_rag(engine):
    """测试完整 RAG 流程"""
    print("\n" + "="*60)
    print("测试 3: 完整 RAG 流程")
    print("="*60)
    
    question = "What does the synthetic release-validation document say?"
    print(f"\n问题: {question}\n")
    
    try:
        result = engine.ask(question)
        
        print("✓ RAG 查询成功\n")
        print("回答:")
        print("-"*60)
        print(result["answer"])
        print("-"*60)
        
        print(f"\n使用模型: {result['model']}")
        print(f"检索结果数: {result['retrieval_count']}")
        print(f"引用来源数: {len(result['sources'])}")
        
        if result['sources']:
            print("\n来源:")
            for i, src in enumerate(result['sources'][:3], 1):
                print(f"  {i}. {src['file']} #chunk_{src['chunk_index']}")
        
    except Exception as e:
        print(f"✗ RAG 查询失败: {e}")
        import traceback
        traceback.print_exc()


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="Run against a disposable synthetic RAG configuration.")
    parser.add_argument("--config", required=True, help="Path to a disposable synthetic YAML config")
    args = parser.parse_args()

    print("\n" + "="*60)
    print("RAG 引擎测试套件")
    print("="*60 + "\n")
    
    # 测试 1: 连接
    engine = test_connection(args.config)
    if not engine:
        print("\n❌ 连接测试失败，终止后续测试")
        return
    
    # 测试 2: 检索
    test_retrieval(engine)
    
    # 测试 3: 完整 RAG
    test_full_rag(engine)
    
    print("\n" + "="*60)
    print("测试完成")
    print("="*60)


if __name__ == "__main__":
    main()
