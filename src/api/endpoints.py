"""API route endpoints"""
import time
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status

from src.audit.models import AuditLogCreate, AuditStage
from src.audit.repository import insert_audit_log
from src.auth.dependencies import get_current_user
from src.auth.models import CurrentUser
from src.core.nl2sql import eval_one
from src.core.sql2summary import summarize_answer
from src.core.answer_grounding import validate_answer_grounding
from src.core.safety_checks import build_safety_checks
from src.models import QueryRequest, QueryResponse
from src.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1", tags=["query"])


@router.get("/health", tags=["health"])
async def health_check():
    """Health check endpoint."""
    logger.info("Health check requested")
    return {"status": "healthy", "service": "NL2SQL Backend"}


@router.post("/query", response_model=QueryResponse, status_code=200)
async def query(
    req: QueryRequest,
    current_user: CurrentUser = Depends(get_current_user),
) -> QueryResponse:
    """
    Process a natural language question through the NL2SQL pipeline.

    Every request writes one row to audit_logs, whether it succeeds,
    fails a known business rule (error/blocked/clarify/no_data), or hits
    an unexpected exception. Audit write failures are fail-open — see
    insert_audit_log().

    `failed_stage` here tracks which post-pipeline step was executing if an
    *unexpected* exception occurs (a bug, not a normal business outcome —
    normal business failures are already returned by eval_one() as
    status="error"/"blocked" with their own failed_stage, with a 200
    response). This is only for the "something we didn't anticipate broke"
    case, so the log line and audit record tell us exactly where instead
    of a bare 500.
    """
    product_type = req.product_type.value
    logger.info(f"Processing query ({product_type}): {req.question}")

    request_id = uuid4()
    start_time = time.perf_counter()
    failed_stage = "sql_pipeline"

    try:
        # Stage: sql_generation / safety_validation / sql_execution
        # (already handled inside eval_one; this only catches an
        # unanticipated exception type slipping through it)
        result = eval_one(req.question, product_type=product_type)

        failed_stage = "answer_generation"
        result = summarize_answer(req.question, result)

        failed_stage = "safety_checks_build"
        result["safety_checks"] = build_safety_checks(
            question=req.question,
            sql=result.get("sql"),
            status=result.get("status"),
            message=result.get("message", ""),
        )

        if result.get("status") == "ok":
            failed_stage = "answer_grounding"
            answer_validation = validate_answer_grounding(
                sql=result.get("sql", ""),
                data=result.get("data", {}),
                final_answer=result.get("final_answer", ""),
            )
            result["safety_checks"]["answer_grounding"] = answer_validation

        logger.info(f"Query processed successfully. Status: {result['status']}")

        failed_stage = "response_generation"
        response = QueryResponse(
            status=result["status"],
            message=result.get("message", ""),
            final_answer=result.get("final_answer"),
            sql=result.get("sql"),
            data=result.get("data"),
            missing_slots=result.get("missing_slots"),
            safety_checks=result.get("safety_checks"),
            meta=result.get("meta"),
        )

        execution_time_ms = int((time.perf_counter() - start_time) * 1000)
        execution_checks = (result.get("safety_checks") or {}).get("execution", {})

        insert_audit_log(AuditLogCreate(
            request_id=request_id,
            user_id=current_user.user_id,
            user_name=current_user.user_name,
            user_role=current_user.role.value,
            question=req.question,
            product_type=product_type,
            generated_sql=result.get("sql"),
            status=result["status"],
            failed_stage=result.get("failed_stage"),
            error_type=result.get("error_type"),
            error_message=result.get("message") if result["status"] in ("error", "blocked") else None,
            result_row_count=len(result["data"]["rows"]) if result.get("data") else None,
            execution_time_ms=execution_time_ms,
            safety_passed=execution_checks.get("connection_stable"),
            permission_granted=execution_checks.get("permission_granted", True),
        ))

        return response

    except Exception as e:
        execution_time_ms = int((time.perf_counter() - start_time) * 1000)
        logger.error(
            f"Query processing failed unexpectedly at stage '{failed_stage}': {e}",
            exc_info=True,
        )

        insert_audit_log(AuditLogCreate(
            request_id=request_id,
            user_id=current_user.user_id,
            user_name=current_user.user_name,
            user_role=current_user.role.value,
            question=req.question,
            product_type=product_type,
            status="error",
            failed_stage=AuditStage(failed_stage),
            error_type=type(e).__name__,
            error_message=str(e),
            execution_time_ms=execution_time_ms,
            permission_granted=True,
        ))

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )
