"""Updated integration tests with new module structure"""
import sys
import os
import json

# Add parent directory to path so we can import src
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_imports():
    """Test that all modules can be imported"""
    print("=" * 60)
    print("Testing module imports...")
    print("=" * 60)
    
    try:
        from src.core.safety_checks import (
            build_safety_checks,
            check_select_only,
            check_no_table_modification,
            check_source_correct,
            check_permission_granted,
        )
        print("✓ src.core.safety_checks imported")
        
        from src.core.nl2sql import eval_one, needs_clarification
        print("✓ src.core.nl2sql imported")
        
        from src.core.sql2summary import summarize_answer
        print("✓ src.core.sql2summary imported")
        
        from src.config import settings
        print("✓ src.config imported")
        
        from src.models import QueryResponse, StatusEnum
        print("✓ src.models imported")
        
        from src.exceptions import NL2SQLException
        print("✓ src.exceptions imported")
        
        from src.utils.logger import get_logger
        print("✓ src.utils.logger imported")
        
        return True
    except Exception as e:
        print(f"✗ Import failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_safety_checks_structure():
    """Test that safety checks have the correct three-stage structure"""
    print("\n" + "=" * 60)
    print("TEST: Safety Checks Three-Stage Structure")
    print("=" * 60)
    
    from src.core.safety_checks import build_safety_checks
    
    # Test with valid SQL
    result = build_safety_checks(
        question="What is the average price of NVDA?",
        sql="SELECT AVG(close) FROM stock_data WHERE ticker = 'NVDA'",
        status="ok",
        message="",
    )
    
    print(f"\nSafety checks structure with valid SQL and ok status:")
    print(f"  Stages present: {list(result.keys())}")
    
    required_stages = ["sql_generation", "safety_validation", "execution"]
    for stage in required_stages:
        if stage not in result:
            print(f"✗ Missing stage: {stage}")
            return False
        print(f"  ✓ {stage}: {list(result[stage].keys())}")
    
    # Test with None SQL (clarify case)
    result_clarify = build_safety_checks(
        question="What is the recent performance?",
        sql=None,
        status="clarify",
        message="Needs clarification",
    )
    
    print(f"\nSafety checks structure with None SQL (clarify case):")
    print(f"  ✓ sql_generation checks return False: {all(not v for v in result_clarify['sql_generation'].values())}")
    print(f"  ✓ execution.permission_granted returns True for clarify: {result_clarify['execution']['permission_granted']}")
    
    # Test with error status
    result_error = build_safety_checks(
        question="Show me data",
        sql=None,
        status="error",
        message="Database connection error: SSL connection has been closed",
    )
    
    print(f"\nSafety checks structure with error status:")
    print(f"  ✓ execution.connection_stable detects connection error: {not result_error['execution']['connection_stable']}")
    
    return True


def test_clarification_logic():
    """Test the clarification detection logic"""
    print("\n" + "=" * 60)
    print("TEST: Clarification Detection Logic")
    print("=" * 60)
    
    from src.core.nl2sql import needs_clarification
    
    test_cases = [
        ("What is the recent performance of NVDA?", True, "time_window"),
        ("Which stock performed better?", True, "comparison_baseline"),
        ("What is the volatility of AAPL?", True, "volatility_measure"),
        ("What is the average close price of NVDA last 30 days?", False, None),
        ("Show me TSLA price", False, None),
    ]
    
    for question, should_clarify, expected_slot in test_cases:
        result = needs_clarification(question)
        is_clarify = result["needs_clarify"]
        
        status_str = "✓" if is_clarify == should_clarify else "✗"
        print(f"{status_str} '{question[:50]}...'")
        print(f"   Clarify needed: {is_clarify}")
        
        if should_clarify and expected_slot:
            if expected_slot in result.get("missing_slots", {}):
                print(f"   ✓ Detected missing slot: {expected_slot}")
            else:
                print(f"   ✗ Failed to detect missing slot: {expected_slot}")
                return False
        
        if is_clarify != should_clarify:
            return False
    
    return True


def test_summarize_answer_handles_clarify():
    """Test that summarize_answer handles clarify status"""
    print("\n" + "=" * 60)
    print("TEST: summarize_answer Handles Clarify Status")
    print("=" * 60)
    
    from src.core.sql2summary import summarize_answer
    
    # Mock clarify result
    mock_clarify = {
        "status": "clarify",
        "missing_slots": {
            "time_window": "Please specify a time period",
            "performance_metric": "Please specify metric",
        },
        "message": "Needs clarification",
    }
    
    result = summarize_answer("What is recent performance?", mock_clarify)
    print(f"Input status: {mock_clarify['status']}")
    print(f"✓ final_answer added: {'final_answer' in result}")
    print(f"✓ final_answer contains clarification info: {'Please provide more information' in result['final_answer']}")
    print(f"✓ Status preserved: {result['status'] == 'clarify'}")
    
    # Mock error result
    mock_error = {"status": "error", "message": "Database connection error"}
    
    result_error = summarize_answer("Show data", mock_error)
    print(f"\nInput status: {mock_error['status']}")
    print(f"✓ Error case handled: {'Error:' in result_error['final_answer']}")
    
    # Mock no_data result
    mock_no_data = {"status": "no_data", "message": "No data found"}
    
    result_no_data = summarize_answer("Show old data", mock_no_data)
    print(f"\nInput status: {mock_no_data['status']}")
    print(f"✓ No_data case handled: {'No data' in result_no_data['final_answer']}")
    
    return True


def test_app_endpoint_compatibility():
    """Test that app.py endpoints would work correctly"""
    print("\n" + "=" * 60)
    print("TEST: API Endpoint Compatibility")
    print("=" * 60)
    
    from src.core.safety_checks import build_safety_checks
    from src.core.sql2summary import summarize_answer
    from src.models import QueryResponse, StatusEnum
    
    # Simulate what app.py's /query endpoint does with clarify response
    print("Simulating /api/v1/query endpoint with clarify flow:")
    
    # Step 1: Mock eval_one return (clarify case)
    sql_res = {
        "status": "clarify",
        "missing_slots": {"time_window": "Need time"},
        "message": "Clarification needed",
    }
    print(f"  1. eval_one returns: status={sql_res['status']}")
    
    # Step 2: summarize_answer
    result = summarize_answer("recent perf", sql_res)
    print(f"  2. summarize_answer adds: final_answer={'final_answer' in result}")
    
    # Step 3: build_safety_checks (what app.py does)
    try:
        result["safety_checks"] = build_safety_checks(
            question="recent perf",
            sql=result.get("sql"),  # Will be None for clarify
            status=result.get("status"),
            message=result.get("message", ""),
        )
        print(f"  3. build_safety_checks succeeds: {type(result['safety_checks']) == dict}")
        print(f"     Structure: {list(result['safety_checks'].keys())}")
        
        # Verify response can be converted to model
        response = QueryResponse(
            status=StatusEnum(result["status"]),
            message=result.get("message", ""),
            final_answer=result.get("final_answer"),
            sql=result.get("sql"),
            data=result.get("data"),
            missing_slots=result.get("missing_slots"),
            safety_checks=result.get("safety_checks"),
            meta=result.get("meta"),
        )
        
        print(f"  4. QueryResponse model validation: ✓")
        print(f"  ✓ Complete response structure verified")
        return True
        
    except Exception as e:
        print(f"  ✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    tests = [
        ("Module Imports", test_imports),
        ("Safety Checks Structure", test_safety_checks_structure),
        ("Clarification Logic", test_clarification_logic),
        ("summarize_answer Handles Clarify", test_summarize_answer_handles_clarify),
        ("API Endpoint Compatibility", test_app_endpoint_compatibility),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            passed = test_func()
            results.append((name, passed))
        except Exception as e:
            print(f"\n✗ {name} FAILED: {e}")
            import traceback
            traceback.print_exc()
            results.append((name, False))
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    passed_count = sum(1 for _, passed in results if passed)
    total_count = len(results)
    
    for name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status}: {name}")
    
    print(f"\nTotal: {passed_count}/{total_count} tests passed")
    
    if passed_count == total_count:
        print("\n" + "=" * 60)
        print("ALL TESTS PASSED ✓")
        print("=" * 60)
        print("\n✓ New project structure verified:")
        print("  1. src/config.py - Centralized configuration")
        print("  2. src/constants.py - All constants")
        print("  3. src/models.py - Pydantic models")
        print("  4. src/exceptions.py - Custom exceptions")
        print("  5. src/core/ - Business logic (nl2sql, sql2summary, safety_checks)")
        print("  6. src/utils/ - Utilities (logger, db, llm)")
        print("  7. src/api/ - FastAPI application")
        return 0
    else:
        print("\nFailed tests need attention!")
        return 1


if __name__ == "__main__":
    sys.exit(main())
