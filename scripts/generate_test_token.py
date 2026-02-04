#!/usr/bin/env python3
"""
Generate a test JWT token for testing the UI.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'apps', 'core-api'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'packages', 'db'))

from jwt_utils import create_agent_token_v2
from database import get_raw_db

def main():
    # Get the test agent from DB
    with get_raw_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT id, moltbook_id, reputation FROM agents WHERE moltbook_id = %s", ("test_agent_001",))
        result = cur.fetchone()
        
        if not result:
            print("Error: Test agent not found. Run setup_test_data.py first.")
            sys.exit(1)
        
        agent_id, moltbook_id, reputation = result
        
    # Generate token
    token = create_agent_token_v2(
        agent_id=str(agent_id),
        moltbook_id=moltbook_id,
        reputation=int(reputation) if reputation else 100
    )
    
    print("=" * 60)
    print("Test JWT Token Generated")
    print("=" * 60)
    print(f"\nAgent ID: {agent_id}")
    print(f"Moltbook ID: {moltbook_id}")
    print(f"\nToken:\n{token}")
    print("\n" + "=" * 60)
    print("Use this token to login to the UI (paste it in the login form)")
    print("=" * 60)

if __name__ == "__main__":
    main()
