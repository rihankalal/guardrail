import os
import json
from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance, PointStruct
from langchain_text_splitters import RecursiveCharacterTextSplitter

client = QdrantClient(url="http://localhost:6333")
model = SentenceTransformer("all-MiniLM-L6-v2")

client.recreate_collection(
    collection_name="real_docs",
    vectors_config=VectorParams(size=384, distance=Distance.COSINE),
)

splitter = RecursiveCharacterTextSplitter(chunk_size=300, chunk_overlap=50)

with open("classifications.json", "r") as f:
    classifications = json.load(f)

docs_folder = "docs"
point_id = 0
points = []

for filename in os.listdir(docs_folder):
    filepath = os.path.join(docs_folder, filename)
    with open(filepath, "r", encoding="utf-8") as f:
        text = f.read()

    chunks = splitter.split_text(text)
    classification = classifications.get(filename, "Internal")  # default if not listed
    print(f"{filename} ({classification}) → split into {len(chunks)} chunks")

    for chunk in chunks:
        embedding = model.encode(chunk)
        points.append(
            PointStruct(
                id=point_id,
                vector=embedding.tolist(),
                payload={
                    "text": chunk,
                    "source": filename,
                    "classification": classification,
                },
            )
        )
        point_id += 1

client.upsert(collection_name="real_docs", points=points)
print(f"\nUploaded {len(points)} total chunks to Qdrant.")