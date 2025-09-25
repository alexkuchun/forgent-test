from typing import Any, Dict, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Run, Response, Evaluation, Question, Condition
from ..schemas import RunResponse

router = APIRouter(prefix="/api/internal", tags=["internal"])


@router.post("/runs/{run_id}/status")
def update_run_status(
    run_id: UUID,
    payload: Dict[str, Any],
    db: Session = Depends(get_db)
):
    run = db.query(Run).filter(Run.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    
    status = payload.get("status")
    if status == "PROCESSING":
        run.status = "processing"
        run.started_at = db.execute("SELECT NOW()").scalar()
    elif status == "FAILED":
        run.status = "failed"
        run.finished_at = db.execute("SELECT NOW()").scalar()
    
    db.commit()
    return {"status": "updated"}


@router.post("/runs/{run_id}/ingest")
def ingest_run_results(
    run_id: UUID,
    payload: Dict[str, Any],
    db: Session = Depends(get_db)
):
    run = db.query(Run).filter(Run.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    
    # Update run status
    run.status = "completed"
    run.finished_at = db.execute("SELECT NOW()").scalar()
    
    # Process prompt results
    prompts = payload.get("prompts", [])
    for prompt_result in prompts:
        prompt_id = prompt_result.get("prompt_id")
        prompt_type = prompt_result.get("prompt_type")
        
        if prompt_type == "QUESTION":
            question = db.query(Question).filter(Question.id == prompt_id).first()
            if question:
                response = Response(
                    run_id=run.id,
                    question_id=question.id,
                    answer_text=prompt_result.get("answer_text") or "",
                    confidence=prompt_result.get("confidence"),
                    response_metadata={
                        "evidence": prompt_result.get("evidence"),
                        "page_refs": prompt_result.get("page_refs", []),
                        "status": prompt_result.get("status"),
                        "error": prompt_result.get("error"),
                    }
                )
                db.add(response)
        
        elif prompt_type == "CONDITION":
            condition = db.query(Condition).filter(Condition.id == prompt_id).first()
            if condition:
                evaluation = Evaluation(
                    run_id=run.id,
                    condition_id=condition.id,
                    result_boolean=prompt_result.get("boolean_result"),
                    rationale_text=prompt_result.get("evidence"),
                    confidence=prompt_result.get("confidence"),
                    evaluation_metadata={
                        "page_refs": prompt_result.get("page_refs", []),
                        "status": prompt_result.get("status"),
                        "error": prompt_result.get("error"),
                    }
                )
                db.add(evaluation)
    
    db.commit()
    return {"status": "ingested"}
