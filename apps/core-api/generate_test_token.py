
import sys
import os
# Ensure we can import locally
sys.path.append(os.getcwd())
try:
    from jwt_utils import create_agent_token
except ImportError:
    # Try assuming we are in apps/core-api
    sys.path.append(os.path.join(os.getcwd(), 'apps/core-api'))
    from apps.core_api.jwt_utils import create_agent_token

agent_id = "6cc8d045-5fbf-4d8f-91ca-59a8134ec9e6"
moltbook_id = "test-moltbook-id"
token = create_agent_token(agent_id, moltbook_id, reputation=100)
print(token)
