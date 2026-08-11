from qdrant_client import QdrantClient, models
import requests

client = QdrantClient(path="./qdrant_data")
print("点数量:", client.count("personal_kb").count)

resp = requests.post(
    "http://localhost:11434/api/embeddings",
    json={"model": "bge-m3", "prompt": "银发族外观喜好"},
    timeout=10
)
vec = resp.json()["embedding"]
print("Ollama OK，向量维度:", len(vec))

# 新版用 query_points
results = client.query_points(
    collection_name="personal_kb",
    query=vec,
    limit=3
).points

print(f"\n查询结果（共{len(results)}条）:")
for r in results:
    print(f"\nscore: {r.score:.3f}")
    print(r.payload.get("text", "")[:150])