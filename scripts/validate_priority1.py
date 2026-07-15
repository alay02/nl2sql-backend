#!/usr/bin/env python
"""
Quick validation script for Priority 1 optimizations
Tests all 3 features: Few-Shot, Validation, Insights
"""

import sys
sys.path.insert(0, '/Users/simacbooki/Desktop/siCUki/si上课ki/AI in Finance/blackrock_nl2sql')

from src.core.nl2sql import SQLValidator, SQLCorrector
from src.core.sql2summary import InsightsExtractor

def test_validator():
    """Test SQLValidator"""
    print("=" * 60)
    print("TEST 1: SQLValidator (1.2 - Self-Validation)")
    print("=" * 60)
    
    validator = SQLValidator()
    
    # Test case 1: Aggregation without GROUP BY
    bad_sql = "SELECT ticker, AVG(close) FROM stock_data WHERE ticker='NVDA'"
    result1 = validator.validate(bad_sql)
    print(f"\nTest 1a - Missing GROUP BY:")
    print(f"  SQL: {bad_sql}")
    print(f"  Valid: {result1['valid']}")
    print(f"  Issues: {result1['issues']}")
    
    # Test case 2: Using NOW()
    bad_sql2 = "SELECT close FROM stock_data WHERE timestamp > NOW() - interval '30 days'"
    result2 = validator.validate(bad_sql2)
    print(f"\nTest 1b - Using NOW():")
    print(f"  SQL: {bad_sql2}")
    print(f"  Valid: {result2['valid']}")
    print(f"  Issues: {result2['issues']}")
    
    # Test case 3: Good SQL
    good_sql = "SELECT ticker, AVG(close) FROM stock_data WHERE ticker='NVDA' GROUP BY ticker LIMIT 10"
    result3 = validator.validate(good_sql)
    print(f"\nTest 1c - Good SQL (with GROUP BY):")
    print(f"  SQL: {good_sql}")
    print(f"  Valid: {result3['valid']}")
    print(f"  Issues: {result3['issues']}")
    

def test_insights():
    """Test InsightsExtractor"""
    print("\n" + "=" * 60)
    print("TEST 2: InsightsExtractor (1.3 - Insights Extraction)")
    print("=" * 60)
    
    extractor = InsightsExtractor()
    
    # Mock data: AAPL prices
    columns = ["date", "close", "volume"]
    rows = [
        ["2025-01-20", 175.30, 52000000],
        ["2025-01-21", 176.50, 48500000],
        ["2025-01-22", 178.20, 51200000],
        ["2025-01-23", 177.60, 49800000],
        ["2025-01-24", 180.50, 55300000],  # Peak
    ]
    
    insights = extractor.extract_insights(columns, rows)
    print(f"\nExtracted Insights from AAPL price data:")
    print(f"  Max: {insights['max']}")
    print(f"  Min: {insights['min']}")
    print(f"  Avg: {insights['avg']}")
    print(f"  Trend: {insights['trend']}")
    print(f"  Volatility: {insights['volatility']}")
    
    insights_text = extractor.format_insights_text(insights)
    print(f"\nFormatted Insights (for LLM context):")
    print(insights_text)


def test_few_shot_prompt():
    """Check Few-Shot examples are in prompt template"""
    print("\n" + "=" * 60)
    print("TEST 3: Few-Shot Examples (1.1 - Few-Shot Learning)")
    print("=" * 60)
    
    from src.constants import SQL_GENERATION_PROMPT_TEMPLATE
    
    # Check for examples
    has_good_examples = "GOOD EXAMPLES" in SQL_GENERATION_PROMPT_TEMPLATE
    has_bad_examples = "BAD EXAMPLES" in SQL_GENERATION_PROMPT_TEMPLATE
    has_example1 = "Example 1" in SQL_GENERATION_PROMPT_TEMPLATE
    
    print(f"\nFew-Shot Template Analysis:")
    print(f"  Has GOOD EXAMPLES section: {has_good_examples}")
    print(f"  Has BAD EXAMPLES section: {has_bad_examples}")
    print(f"  Has specific examples: {has_example1}")
    
    if has_good_examples:
        # Extract snippet
        start = SQL_GENERATION_PROMPT_TEMPLATE.find("GOOD EXAMPLES")
        end = SQL_GENERATION_PROMPT_TEMPLATE.find("Schema:", start)
        snippet = SQL_GENERATION_PROMPT_TEMPLATE[start:end][:300]
        print(f"\nPrompt Template Snippet (first 300 chars):")
        print(f"  {snippet.replace(chr(10), chr(10) + '  ')}...")
    

def test_integration():
    """Test that all components are properly integrated"""
    print("\n" + "=" * 60)
    print("TEST 4: Integration Check")
    print("=" * 60)
    
    try:
        # Check nl2sql imports
        from src.core.nl2sql import SQLValidator, SQLCorrector
        print("\n✅ SQLValidator and SQLCorrector imported successfully from nl2sql.py")
        
        # Check sql2summary imports
        from src.core.sql2summary import InsightsExtractor
        print("✅ InsightsExtractor imported successfully from sql2summary.py")
        
        # Check constants
        from src.constants import SQL_GENERATION_PROMPT_TEMPLATE
        print("✅ SQL_GENERATION_PROMPT_TEMPLATE imported successfully from constants.py")
        
        # Verify instances can be created
        validator = SQLValidator()
        corrector = SQLCorrector()
        extractor = InsightsExtractor()
        print("✅ All classes can be instantiated")
        
        print("\n✅ All integration checks passed!")
        return True
        
    except Exception as e:
        print(f"❌ Integration check failed: {e}")
        return False


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("PRIORITY 1 OPTIMIZATION VALIDATION")
    print("Testing: 1.1 Few-Shot, 1.2 Validation, 1.3 Insights")
    print("=" * 60)
    
    # Run tests
    test_integration()
    test_validator()
    test_insights()
    test_few_shot_prompt()
    
    print("\n" + "=" * 60)
    print("✅ ALL VALIDATION TESTS COMPLETE")
    print("=" * 60)
