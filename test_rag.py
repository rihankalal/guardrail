from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
import requests

client = QdrantClient(url="http://localhost:6333")
model = SentenceTransformer("all-MiniLM-L6-v2")

def ask_question(question: str):
    question_embedding = model.encode(question)
    results = client.query_points(
        collection_name="real_docs",
        query=question_embedding.tolist(),
        limit=1,
    )
    top_result = results.points[0]
    context = top_result.payload["text"]
    source = top_result.payload["source"]
    print(f"Question: {question}")
    print(f"Retrieved from: {source}")
    print(f"Context: {context}")

    prompt = f"""Answer the question using ONLY the context below. If the context doesn't contain the answer, say so.

Context: {context}

Question: {question}

Answer:"""

    response = requests.post(
        "http://localhost:11434/api/generate",
        json={
            "model": "llama3.1:8b-instruct-q4_K_M",
            "prompt": prompt,
            "stream": False,
        },
    )

    answer = response.json()["response"]
    print(f"Answer: {answer}")
    print("-" * 50)

ask_question("How many sick days do I get?")
ask_question("Can I install any software I want on my work laptop?")