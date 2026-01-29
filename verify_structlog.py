#!/usr/bin/env python3
"""Quick verification script for structlog integration.

This script verifies that:
1. structlog module can be imported
2. monitoring module exports work correctly
3. Loggers can be instantiated
4. Basic logging produces output in both modes

Run: python verify_structlog.py
"""

import sys

def verify_imports():
    """Verify all imports work."""
    print("1. Testing imports...")
    try:
        from nba_betting_agent.monitoring import configure_logging, get_logger, bind_correlation_id
        print("   ✓ monitoring module imports work")
    except ImportError as e:
        print(f"   ✗ Import failed: {e}")
        return False

    return True


def verify_logging():
    """Verify logging configuration and output."""
    from nba_betting_agent.monitoring import configure_logging, get_logger

    print("\n2. Testing development mode logging...")
    configure_logging("development")
    log = get_logger()
    log.info("test_event", key="value", count=42)
    print("   ✓ Development mode works (colored output above)")

    print("\n3. Testing production mode logging...")
    configure_logging("production")
    log = get_logger()
    log.info("test_event_json", key="value", count=42)
    print("   ✓ Production mode works (JSON output above)")

    return True


def verify_agent_imports():
    """Verify agent files import correctly with structlog."""
    print("\n4. Testing agent imports...")

    try:
        from nba_betting_agent.agents.lines_agent.api.odds_api import OddsAPIClient
        print("   ✓ odds_api.py imports correctly")
    except Exception as e:
        print(f"   ✗ odds_api.py import failed: {e}")
        return False

    try:
        from nba_betting_agent.agents.stats_agent.agent import collect_stats
        print("   ✓ stats_agent.py imports correctly")
    except Exception as e:
        print(f"   ✗ stats_agent.py import failed: {e}")
        return False

    try:
        from nba_betting_agent.agents.analysis_agent.agent import analyze_bets
        print("   ✓ analysis_agent.py imports correctly")
    except Exception as e:
        print(f"   ✗ analysis_agent.py import failed: {e}")
        return False

    return True


if __name__ == "__main__":
    print("=" * 60)
    print("Structlog Integration Verification")
    print("=" * 60)

    success = True

    if not verify_imports():
        success = False

    if success and not verify_logging():
        success = False

    if success and not verify_agent_imports():
        success = False

    print("\n" + "=" * 60)
    if success:
        print("✓ All verifications passed!")
        print("=" * 60)
        sys.exit(0)
    else:
        print("✗ Some verifications failed")
        print("=" * 60)
        sys.exit(1)
