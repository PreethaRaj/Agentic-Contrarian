import json
import uuid
import datetime
from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.database import init_db
from app.db.session import get_db
from app.db.models import InvestigationReport
from app.agents.graph import run_investigation  # Ensure this path is correct

app = FastAPI()

@app.on_event("startup")
def on_startup():
    init_db()

@app.get("/health")
def health():
    return {"status": "ok"}
def sanitize_for_json(obj):
    """
    Recursively convert state dict to JSON-safe primitives.
    Prevents psycopg2 connection abort caused by non-serialisable values
    (datetime, sets, TypedDict subclasses, Pydantic models, etc.).
    """
    if isinstance(obj, dict):
        return {str(k): sanitize_for_json(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [sanitize_for_json(i) for i in obj]
    if isinstance(obj, (datetime.datetime, datetime.date)):
        return obj.isoformat()
    if isinstance(obj, (set, frozenset)):
        return list(obj)
    if isinstance(obj, (str, int, float, bool)) or obj is None:
        return obj
    # Fallback: coerce unknown types to string rather than crashing
    return str(obj)


@app.get("/report/{report_id}")
def get_public_report(report_id: str, db: Session = Depends(get_db)):
    report = db.query(InvestigationReport).filter(
        InvestigationReport.id == report_id
    ).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return report.state_snapshot


@app.post("/investigate")
def conduct_study(query: str, db: Session = Depends(get_db)):
    try:
        # 1. Run agent graph
        final_state = run_investigation(query)

        # 2. Surface hard-stop from AuditorNode (empty evidence_pool)
        if not final_state.get("evidence_pool") and final_state.get("final_report"):
            # Still persist + return — UI will show the final_report warning message
            pass

        # 3. Sanitise state — removes all non-JSON-serialisable values
        safe_state = sanitize_for_json(final_state)

        # 4. Validate JSON round-trip BEFORE hitting psycopg2
        #    If this raises, we get a clean 500 instead of a TCP abort
        try:
            json.dumps(safe_state)
        except (TypeError, ValueError) as je:
            raise HTTPException(
                status_code=500,
                detail=f"State serialisation failed (bug in agent output): {je}"
            )

        # 5. Persist to Postgres
        report_id = str(uuid.uuid4())
        new_report = InvestigationReport(
            id=report_id,
            query=query,
            state_snapshot=safe_state,
        )
        db.add(new_report)
        db.commit()

        safe_state["report_id"] = report_id
        return safe_state

    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        print(f"[/investigate] Unhandled error: {e}")
        raise HTTPException(status_code=500, detail=f"Investigation failed: {e}")
