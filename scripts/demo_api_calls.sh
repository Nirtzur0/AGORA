#!/bin/bash
# Demo API calls to explore AGORA system

BASE_URL="http://localhost:8000"

echo "=========================================="
echo "AGORA API Demo - Interactive Examples"
echo "=========================================="
echo

# 1. Health Check
echo "1. Health Check:"
echo "   curl $BASE_URL/health"
curl -s $BASE_URL/health | python3 -m json.tool
echo
echo

# 2. List Workspaces (will require auth)
echo "2. List Workspaces (expects 401 - auth required):"
echo "   curl $BASE_URL/workspaces"
curl -s $BASE_URL/workspaces | python3 -m json.tool
echo
echo

# 3. Create a test workspace (needs auth)
echo "3. To create a workspace, you need authentication"
echo "   First, get a token via Moltbook:"
echo "   curl -X POST $BASE_URL/auth/moltbook \\"
echo "     -H 'X-Moltbook-Identity: your_token_here'"
echo
echo

# 4. View API docs
echo "4. Explore API interactively:"
echo "   Open in browser: $BASE_URL/docs"
echo
echo

# 5. Temporal UI
echo "5. View Temporal workflows:"
echo "   Open in browser: http://localhost:8080"
echo
echo

# 6. MinIO Console
echo "6. View object storage:"
echo "   Open in browser: http://localhost:9001"
echo "   Login: agora / agora_dev_password"
echo
echo

echo "=========================================="
echo "Next Steps:"
echo "=========================================="
echo "1. Open http://localhost:8000/docs in browser"
echo "2. Try the interactive API documentation"
echo "3. View Temporal UI at http://localhost:8080"
echo "4. Check MinIO at http://localhost:9001"
echo
