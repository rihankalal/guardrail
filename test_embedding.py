from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance, PointStruct

# Connect to your running Qdrant container
client = QdrantClient(url="http://localhost:6333")

# Load the embedding model
model = SentenceTransformer("all-MiniLM-L6-v2")

# Create a "collection" (like a table) to store our vectors
client.recreate_collection(
    collection_name="test_docs",
    vectors_config=VectorParams(size=384, distance=Distance.COSINE),
)

# Some sample chunks (pretend these are pieces of company documents)
chunks = [
    "Employees get 18 days of paid annual leave.",
    "Senior Software Engineers earn between 18 and 24 lakhs annually.",
    "Visitors must register at reception and be escorted at all times.",
]

# Embed and upload each chunk
embeddings = model.encode(chunks)

points = [
    PointStruct(id=i, vector=embeddings[i].tolist(), payload={"text": chunks[i]})
    for i in range(len(chunks))
]

client.upsert(collection_name="test_docs", points=points)

print(f"Uploaded {len(chunks)} chunks to Qdrant.")

# Now search: ask a question and find the closest chunk
question = "How many vacation days do I get?"
question_embedding = model.encode(question)

results = client.query_points(
    collection_name="test_docs",
    query=question_embedding.tolist(),
    limit=2,
)

print(f"\nQuestion: {question}")
print("Top matches:")
for r in results.points:
    print(f"  Score: {r.score:.4f} — {r.payload['text']}")