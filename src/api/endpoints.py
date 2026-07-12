"""API route endpoints"""
from fastapi import APIRouter, HTTPException, status

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
async def query(req: QueryRequest) -> QueryResponse:
    """
    Process a natural language question through the NL2SQL pipeline.

    `failed_stage` here tracks which post-pipeline step was executing if an
    *unexpected* exception occurs (a bug, not a normal business outcome —
    normal business failures are already returned by eval_one() as
    status="error"/"blocked" with their own failed_stage, with a 200
    response). This is only for the "something we didn't anticipate broke"
    case, so the log line tells us exactly where instead of a bare 500.
    """
    product_type = req.product_type.value
    logger.info(f"Processing query ({product_type}): {req.question}")

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
        return QueryResponse(
            status=result["status"],
            message=result.get("message", ""),
            final_answer=result.get("final_answer"),
            sql=result.get("sql"),
            data=result.get("data"),
            missing_slots=result.get("missing_slots"),
            safety_checks=result.get("safety_checks"),
            meta=result.get("meta"),
        )

    except Exception as e:
        logger.error(
            f"Query processing failed unexpectedly at stage '{failed_stage}': {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )
