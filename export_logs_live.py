from database import SessionLocal, AuditLog
import pandas as pd
import time
from datetime import datetime

REFRESH_SECONDS = 10
FILENAME = "audit_log_export.xlsx"


def export_once():
    session = SessionLocal()
    logs = session.query(AuditLog).order_by(AuditLog.timestamp.desc()).all()
    session.close()

    data = [
        {
            "Timestamp": log.timestamp,
            "Username": log.username,
            "Role": log.role,
            "Question": log.question,
            "Retrieved Source": log.retrieved_source,
            "Document Classification": log.retrieved_classification,
            "Access Denied": log.access_denied,
            "PII Redacted Count": log.redacted_count,
            "Guardrail Status": log.guardrail_status,
            "Answer Preview": log.answer_preview,
        }
        for log in logs
    ]

    df = pd.DataFrame(data)

    try:
        df.to_excel(FILENAME, index=False, engine="openpyxl")
        denied_count = df["Access Denied"].sum() if not df.empty else 0
        print(
            f"[{datetime.now().strftime('%H:%M:%S')}] "
            f"Exported {len(data)} entries ({denied_count} denied) → {FILENAME}"
        )
    except PermissionError:
        print(
            f"[{datetime.now().strftime('%H:%M:%S')}] "
            f"Skipped — {FILENAME} is open in Excel and locked. Close it to allow the next write."
        )


if __name__ == "__main__":
    print(f"Auto-exporting audit log to {FILENAME} every {REFRESH_SECONDS}s. Press Ctrl+C to stop.")
    while True:
        export_once()
        time.sleep(REFRESH_SECONDS)