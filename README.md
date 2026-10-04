# GuardRail RAG

A secure, role-aware Retrieval-Augmented Generation (RAG) system built from scratch to explore how access control, privacy protection, and output validation can be enforced architecturally in an LLM pipeline — rather than relying on prompt instructions alone.

This is a solo learning build: a personal reimplementation of a team academic project (same name, independent codebase), built to understand RAG and LLM security concepts hands-on, end to end, running entirely on local hardware (no cloud APIs).

## Why This Exists

Conventional RAG systems retrieve documents purely on semantic similarity — they have no concept of *who* is asking. An intern's ordinary question could surface a confidential salary report if it happens to be the closest semantic match, and relying on prompt instructions like "don't reveal this" is fragile, since prompt injection can make a model ignore its own rules.

GuardRail RAG treats authorization and privacy as properties of the data pipeline itself. Every request passes through three independent security layers before a response is ever generated.

## Architecture — Three Security Layers

**Layer 1 — Retrieval-Time RBAC**
Every document chunk is tagged with a classification level (Public, Internal, Confidential, Restricted) at ingestion time. Each user role is mapped to the levels it's cleared for. Access checks happen *before* retrieval — unauthorized documents are excluded from the candidate set at the database query level, not filtered out afterward.

**Layer 2 — Pre-Generation PII Redaction**
Retrieved content — even content the user is authorized to see — is scanned for personally identifiable information (names, emails, phone numbers) using Microsoft Presidio. Detected PII is masked *before* it ever reaches the LLM, so the model cannot leak what it was never shown.

**Layer 3 — Post-Generation Output Validation**
A second, independent LLM call checks the generated answer against the source context for factual accuracy — catching unsupported claims or misleading interpretations (e.g., silently summing separate figures into an implied total) before the response reaches the user.

**Plus — Audit Logging & Threshold Flagging**
Every query is logged (user, role, retrieved source, access decision, redaction count, guardrail outcome) to a SQLite audit trail. A threshold-based detection layer flags any user who is repeatedly denied access within a short time window, surfacing a live list of flagged accounts through an admin-only endpoint.

## Request Flow

```
User → Login (JWT issued) → Question submitted with token
     → Role extracted from verified token
     → Vector search filtered by role's allowed classification levels   [Layer 1]
     → If no authorized match exists → honest "access denied" response
     → Retrieved content scanned and PII masked                        [Layer 2]
     → LLM generates an answer from the redacted context
     → Second LLM pass validates the answer against the context        [Layer 3]
     → Every decision logged to the audit trail
     → Response (+ source, redaction count, guardrail status) returned
```

## Tech Stack

| Component | Tool | Why |
|---|---|---|
| Backend | FastAPI | Async, auto-generated API docs |
| Embeddings | sentence-transformers (`all-MiniLM-L6-v2`) | Lightweight, runs locally |
| Vector database | Qdrant | Native metadata filtering — the enforcement mechanism for Layer 1 |
| LLM | Llama 3.1 8B via Ollama | Free, fully local, no data leaves the machine |
| PII detection | Microsoft Presidio | Purpose-built entity recognition and anonymization |
| Auth | JWT (python-jose) | Stateless, tamper-evident role claims |
| Frontend | Streamlit | Fast, functional chat interface |
| Audit storage | SQLite + SQLAlchemy | Zero-infrastructure, real SQL querying |

## Project Structure

```
guardrail-rag-solo/
├── main.py                       # FastAPI backend — all three security layers
├── app.py                        # Streamlit frontend
├── ingest.py                     # Document chunking + embedding + Qdrant upload
├── database.py                   # Audit logging + threshold flagging
├── security.py                   # JWT creation/validation
├── users.py                      # Mock user store + role clearance mapping
├── export_logs_live.py           # Auto-refreshing Excel export of the audit log
├── run_evaluation.py             # Automated multi-role test suite
├── classifications.json          # Document → classification level mapping
├── docs/                         # 19-document mock enterprise dataset
└── test_*.py                     # Standalone scripts used while building each layer
```

## Demo Accounts

| Username | Role | Clearance |
|---|---|---|
| `carol` | Intern | Public, Internal |
| `bob` | Employee | Public, Internal |
| `admin` | Admin | Public, Internal, Confidential, Restricted |

(Password for all: `password123` — mock credentials for local demo purposes only.)

## Running It Locally

**Prerequisites:** Python 3.13, Docker Desktop, [Ollama](https://ollama.com)

```powershell
# 1. Start Qdrant
docker run -d --name qdrant -p 6333:6333 -p 6334:6334 qdrant/qdrant

# 2. Pull the model
ollama pull llama3.1:8b-instruct-q4_K_M

# 3. Set up the environment
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt   # or install packages individually — see below

# 4. Ingest the document set
python ingest.py

# 5. Start the backend
uvicorn main:app --reload

# 6. In a separate terminal, start the frontend
streamlit run app.py
```

Backend docs available at `http://localhost:8000/docs`. Frontend at `http://localhost:8501`.

## What This Demonstrates

Live, testable proof — not just architectural claims:

- The same question, asked by `carol` (intern) and `admin`, produces fundamentally different outcomes: `carol` receives an honest access-denial message naming the required clearance level, while `admin` receives the real answer.
- PII redaction applies regardless of role — even `admin`'s authorized access to a document containing a name, email, and phone number results in those values being masked before the LLM generates a response.
- A full automated evaluation run (36 queries across 3 roles) is reproducible via `run_evaluation.py`, producing real metrics — access-denial rate, PII redaction rate, guardrail pass rate, and average latency — rather than relying on anecdotal testing.

## Known Limitations

- Retrieval accuracy depends on embedding similarity and can occasionally route an ambiguous question to a less-ideal document, particularly with a small document corpus.
- The output-validation layer (Layer 3) uses the same local 8B model as generation, which is less reliable at nuanced self-critique than larger models — this was observed directly during development and is documented as a known constraint rather than a solved problem.
- This is a learning/prototype build: authentication uses a mock in-memory user store, not a production identity provider.

## Background

This project was built solo, from zero prior experience with Python, Docker, or RAG, as a hands-on way to understand retrieval-augmented generation and LLM security concepts by implementing them directly rather than only reading about them. It parallels — but is independently implemented from — a team academic project of the same name.
