#!/usr/bin/env python3
"""
Evaluation harness runner - Component 24

CLI tool to run MVP success criteria checks and regression tests.

Usage:
    python scripts/run_evaluation.py [--verbose] [--no-color]
    
Exit codes:
    0 = all tests passed
    1 = one or more tests failed
    2 = error running harness

Per spec §1 MVP success criteria and §5.10 MVP minimal subset.
"""

import sys
import os
import asyncio
import argparse
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from tests.evaluation_harness import run_evaluation_harness
from packages.db.session import get_async_session


def print_banner():
    """Print evaluation harness banner."""
    print("\n" + "=" * 80)
    print("AGORA MVP Evaluation Harness - Component 24")
    print("Automated testing for MVP success criteria and regression prevention")
    print("=" * 80 + "\n")


def print_summary(results: dict, verbose: bool = False):
    """Print evaluation results summary."""
    passed = results['tests_passed']
    failed = results['tests_failed']
    total = passed + failed
    
    print("\n" + "=" * 80)
    print("EVALUATION RESULTS")
    print("=" * 80)
    print(f"Total Tests:  {total}")
    print(f"Passed:       {passed} ✓")
    print(f"Failed:       {failed} {'✗' if failed > 0 else ''}")
    print(f"Success Rate: {(passed/total*100) if total > 0 else 0:.1f}%")
    
    if failed > 0:
        print("\nFAILURES:")
        for failure in results['failures']:
            print(f"  ✗ {failure}")
    
    print("=" * 80)
    
    if verbose and results.get('timestamp'):
        print(f"\nRun timestamp: {results['timestamp']}")
    
    print()


async def run_harness(verbose: bool = False) -> int:
    """
    Run evaluation harness against current database state.
    
    Returns:
        Exit code (0=success, 1=failures, 2=error)
    """
    try:
        async for session in get_async_session():
            print_banner()
            
            if verbose:
                print("Running MVP success criteria checks...")
                print("- Citation coverage/resolution = 100%")
                print("- Critique existence and resolution")
                print("- No orphan statements")
                print("\nRunning negative regression tests...")
                print("- Uncited claim blocks finalization")
                print("- Forbidden action rejected")
                print("- Unresolvable evidence fails\n")
            
            # Run evaluation harness
            results = await run_evaluation_harness(session)
            
            # Print results
            print_summary(results, verbose=verbose)
            
            # Return exit code
            if results['tests_failed'] == 0:
                print("✓ All MVP success criteria met. System ready for production.")
                return 0
            else:
                print("✗ MVP success criteria not met. Review failures above.")
                return 1
                
    except Exception as e:
        print(f"\n✗ ERROR: Failed to run evaluation harness: {e}", file=sys.stderr)
        if verbose:
            import traceback
            traceback.print_exc()
        return 2


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Run AGORA MVP evaluation harness",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run with default settings
  python scripts/run_evaluation.py
  
  # Run with verbose output
  python scripts/run_evaluation.py --verbose
  
  # Run in CI (no color output)
  python scripts/run_evaluation.py --no-color

Exit codes:
  0 = all tests passed
  1 = one or more tests failed  
  2 = error running harness
        """
    )
    
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Enable verbose output'
    )
    
    parser.add_argument(
        '--no-color',
        action='store_true',
        help='Disable colored output (for CI)'
    )
    
    args = parser.parse_args()
    
    # Run evaluation harness
    exit_code = asyncio.run(run_harness(verbose=args.verbose))
    
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
