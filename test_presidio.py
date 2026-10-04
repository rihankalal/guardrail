from presidio_analyzer import AnalyzerEngine
from presidio_anonymizer import AnonymizerEngine

analyzer = AnalyzerEngine()
anonymizer = AnonymizerEngine()

text = "For payroll queries, contact Priya Sharma at priya.sharma@guardrailcorp.com or call +91-98765-43210."

# Step 1: find PII
results = analyzer.analyze(text=text, language="en")
print("Detected entities:")
for r in results:
    print(f"  {r.entity_type}: '{text[r.start:r.end]}' (confidence: {r.score:.2f})")

# Step 2: mask it
anonymized = anonymizer.anonymize(text=text, analyzer_results=results)
print("\nOriginal: ", text)
print("Redacted:", anonymized.text)