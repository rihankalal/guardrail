from fastapi import FastAPI, Depends, HTTPException, Header
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchAny
from presidio_analyzer import AnalyzerEngine
from presidio_anonymizer import AnonymizerEngine
import requests

from users import verify_user, ROLE_CLEARANCE
from security import create_token, decode_token
from database import init_db, log_query, get_blocked_count_for_user, get_all_flagged_users

app = FastAPI(title="GuardRail RAG - Solo Build")

init_db()

client = QdrantClient(url="http://localhost:6333")
model = SentenceTransformer("all-MiniLM-L6-v2")

pii_analyzer = AnalyzerEngine()
pii_anonymizer = AnonymizerEngine()

OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "llama3.1:8b-instruct-q4_K_M"

FLAG_THRESHOLD = 3
FLAG_WINDOW_MINUTES = 5


class LoginRequest(BaseModel):
    username: str
    password: str


class QueryRequest(BaseModel):
    question: str


def call_ollama(prompt: str) -> str:
    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,
                "keep_alive": "30m",
            },
            timeout=120,
        )
        response.raise_for_status()
        data = response.json()
        if "response" not in data:
            raise ValueError(f"Ollama returned unexpected format: {data}")
        return data["response"]
    except (requests.exceptions.RequestException, ValueError) as e:
        print(f"ERROR - Ollama call failed: {e}")
        raise HTTPException(
            status_code=503,
            detail="The AI model is temporarily unavailable. Please try again in a moment.",
        )


def check_groundedness(context: str, question: str, answer: str) -> dict:
    check_prompt = f"""You are checking an AI answer for factual accuracy against a source document.
Note: the context may contain privacy placeholders like <PERSON>, <EMAIL_ADDRESS>, or <PHONE_NUMBER> — treat these as valid, expected content.

Question asked: {question}

Context: {context}

Answer: {answer}

Check specifically for these issues:
1. Does the answer state any fact or number NOT present in the context?
2. Does the answer combine, sum, or total separate figures from the context, when the context does NOT explicitly state that total itself?

If either issue is present, respond with exactly: UNGROUNDED
If the answer only restates facts from the context without adding unstated sums or claims, respond with exactly: GROUNDED

Respond with ONLY one word."""

    full_response = call_ollama(check_prompt)
    print(f"DEBUG - Full groundedness response:\n{full_response}\n---")
    last_word = full_response.strip().split()[-1].upper().strip(".:")
    is_grounded = last_word == "GROUNDED"

    return {"grounded": is_grounded, "raw_verdict": full_response}


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.post("/login")
def login(request: LoginRequest):
    user = verify_user(request.username, request.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid username or password")
    token = create_token(user["username"], user["role"])
    return {"access_token": token, "role": user["role"]}


def get_current_user(authorization: str = Header(...)):
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header")
    token = authorization.removeprefix("Bearer ").strip()
    payload = decode_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return payload


@app.get("/admin/security-alerts")
def security_alerts(current_user: dict = Depends(get_current_user)):
    """Admin-only: lists users who have been blocked repeatedly in the recent window."""
    if current_user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin access required.")
    flagged = get_all_flagged_users(minutes=FLAG_WINDOW_MINUTES, threshold=FLAG_THRESHOLD)
    return {
        "window_minutes": FLAG_WINDOW_MINUTES,
        "threshold": FLAG_THRESHOLD,
        "flagged_users": flagged,
    }


@app.post("/query")
def query(request: QueryRequest, current_user: dict = Depends(get_current_user)):
    role = current_user["role"]
    username = current_user["sub"]
    allowed_classifications = ROLE_CLEARANCE.get(role, [])

    question_embedding = model.encode(request.question)

    unfiltered_results = client.query_points(
        collection_name="real_docs",
        query=question_embedding.tolist(),
        limit=1,
    )
    true_best_classification = None
    if unfiltered_results.points:
        true_best_classification = unfiltered_results.points[0].payload.get("classification")

    is_authorization_gap = (
        true_best_classification is not None
        and true_best_classification not in allowed_classifications
    )

    if is_authorization_gap:
        answer = (
            f"Access denied. This information requires '{true_best_classification}' "
            f"clearance, which your role ('{role}') does not have. "
            f"Please contact an administrator if you believe you need access."
        )
        log_query(
            username=username, role=role, question=request.question,
            retrieved_source=None, retrieved_classification=true_best_classification,
            access_denied=True, redacted_count=0, guardrail_status="n/a",
            answer_preview=answer,
        )

        blocked_count = get_blocked_count_for_user(username, minutes=FLAG_WINDOW_MINUTES)
        security_flag = blocked_count >= FLAG_THRESHOLD
        if security_flag:
            print(f"SECURITY ALERT: user '{username}' blocked {blocked_count} times in {FLAG_WINDOW_MINUTES} min")

        return {
            "question": request.question,
            "answer": answer,
            "source": None,
            "your_role": role,
            "redacted_count": 0,
            "guardrail_status": "n/a",
            "access_denied": True,
            "security_flag": security_flag,
        }

    results = client.query_points(
        collection_name="real_docs",
        query=question_embedding.tolist(),
        query_filter=Filter(
            must=[
                FieldCondition(
                    key="classification",
                    match=MatchAny(any=allowed_classifications),
                )
            ]
        ),
        limit=1,
    )

    if not results.points:
        answer = "No relevant information was found for your question."
        log_query(
            username=username, role=role, question=request.question,
            retrieved_source=None, retrieved_classification=None,
            access_denied=False, redacted_count=0, guardrail_status="n/a",
            answer_preview=answer,
        )
        return {
            "question": request.question, "answer": answer, "source": None,
            "your_role": role, "redacted_count": 0, "guardrail_status": "n/a",
            "access_denied": False, "security_flag": False,
        }

    top_result = results.points[0]
    context = top_result.payload["text"]
    source = top_result.payload["source"]
    classification = top_result.payload.get("classification")

    pii_results = pii_analyzer.analyze(
        text=context,
        language="en",
        entities=["PERSON", "EMAIL_ADDRESS", "PHONE_NUMBER"],
    )
    redacted = pii_anonymizer.anonymize(text=context, analyzer_results=pii_results)
    context = redacted.text
    redacted_count = len(pii_results)

    prompt = f"""Answer the question using ONLY the context below. If the context doesn't contain the answer, say so.
If the context lists multiple separate categories or entitlements (such as different types of leave), list each one individually with its own figure.
Do NOT add them together or state a combined total unless the context explicitly provides that total itself.

Context: {context}

Question: {request.question}

Answer:"""

    answer = call_ollama(prompt)

    groundedness = check_groundedness(context, request.question, answer)
    guardrail_status = "passed" if groundedness["grounded"] else "flagged"

    if not groundedness["grounded"]:
        answer = "This response was flagged as potentially ungrounded and has been withheld. Please rephrase your question."

    log_query(
        username=username, role=role, question=request.question,
        retrieved_source=source, retrieved_classification=classification,
        access_denied=False, redacted_count=redacted_count, guardrail_status=guardrail_status,
        answer_preview=answer,
    )

    return {
        "question": request.question,
        "answer": answer,
        "source": source,
        "your_role": role,
        "redacted_count": redacted_count,
        "guardrail_status": guardrail_status,
        "access_denied": False,
        "security_flag": False,
    }