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
    """
    try:
        logger.info(f"Processing query: {req.question}")

        # Step 1: Generate and execute SQL
        sql_result = eval_one(req.question)

        # Step 2: Generate natural-language answer
        result = summarize_answer(req.question, sql_result)

        # Step 3: Build existing SQL / execution safety checks
        result["safety_checks"] = build_safety_checks(
            question=req.question,
            sql=result.get("sql"),
            status=result.get("status"),
            message=result.get("message", ""),
        )

        # Step 4: Validate whether final_answer is grounded in SQL result
        if result.get("status") == "ok":
            answer_validation = validate_answer_grounding(
                sql=result.get("sql", ""),
                data=result.get("data", {}),
                final_answer=result.get("final_answer", ""),
            )
            result["safety_checks"]["answer_grounding"] = answer_validation

        logger.info(f"Query processed successfully. Status: {result['status']}")

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
        logger.error(f"Query processing failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )
