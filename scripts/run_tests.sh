#!/bin/bash
# Test Suite Runner
# Führt alle Tests aus und generiert Report

echo "🧪 KI_ana Test Suite"
echo "===================="

# Run tests in backend container
echo "📦 Backend Tests..."
docker-compose exec -T backend pytest tests/ \
    -v \
    --tb=short \
    --color=yes \
    --maxfail=5 \
    2>&1 | tee test_results_$(date +%Y%m%d_%H%M%S).log

if [ ${PIPESTATUS[0]} -eq 0 ]; then
    echo "✅ Alle Tests bestanden!"
    exit 0
else
    echo "❌ Einige Tests sind fehlgeschlagen"
    echo "📄 Siehe test_results_*.log für Details"
    exit 1
fi
