#!/usr/bin/env python3
"""
Generate a test JWT token for testing the UI.
Uses /auth/moltbook to avoid direct DB dependencies.
"""
import os
import requests

def main():
    base_url = os.getenv("BASE_URL", "http://localhost:8000")
    identity = os.getenv("MOLTBOOK_IDENTITY", "debug-token-clawdbot")

    response = requests.post(
        f"{base_url}/auth/moltbook",
        headers={"X-Moltbook-Identity": identity},
        timeout=5,
    )
    if response.status_code != 200:
        raise SystemExit(
            f"Error: auth failed ({response.status_code}) {response.text}"
        )

    data = response.json()
    token = data["agent_session_jwt"]
    agent_id = data["agent_id"]
    moltbook_id = data["moltbook_id"]
    
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
