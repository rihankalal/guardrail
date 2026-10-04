from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue
from presidio_analyzer import AnalyzerEngine
from presidio_anonymizer import AnonymizerEngine

client = QdrantClient(url="http://localhost:6333")
analyzer = AnalyzerEngine()
anonymizer = AnonymizerEngine()

results, _ = client.scroll(
    collection_name="real_docs",
    scroll_filter=Filter(
        must=[FieldCondition(key="source", match=MatchValue(value="hr_contact.txt"))]
    ),
    limit=5,
)

print(f"Found {len(results)} chunk(s) from hr_contact.txt\n")

for point in results:
    text = point.payload["text"]
    print("Original chunk:", text)

    pii_results = analyzer.analyze(text=text, language="en")
    redacted = anonymizer.anonymize(text=text, analyzer_results=pii_results)

    print("Redacted:", redacted.text)
    print(f"PII found: {len(pii_results)}")
    print("-" * 50)