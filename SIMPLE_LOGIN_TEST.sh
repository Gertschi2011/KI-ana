#!/bin/bash
# Simple Login Test - No hanging Python commands

echo "🧪 Simple Login Test"
echo "================================"

# Test 1: Backend Health
echo "1. Backend Health:"
curl -s http://localhost:8000/health | head -1
echo ""

# Test 2: Login with curl (no Python!)
echo "2. Login Test:"
curl -s -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  --data-binary '{"username":"Gerald","password":"Jawohund2011!","remember":false}' \
  | jq -r 'if .ok then "✅ LOGIN SUCCESS - User: " + .user.username else "❌ FAILED: " + .detail end' 2>/dev/null || echo "Parse error"

echo ""
echo "================================"
