#!/bin/bash
# Test runner script for KI_ana

set -e  # Exit on error

echo "=========================================="
echo "KI_ana Test Suite"
echo "=========================================="

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if pytest is installed
if ! command -v pytest &> /dev/null; then
    echo -e "${RED}❌ pytest not found${NC}"
    echo "Installing test dependencies..."
    pip install -r requirements-test.txt
fi

# Run tests based on argument
case "${1:-all}" in
    "all")
        echo -e "${YELLOW}Running all tests...${NC}"
        pytest tests/ -v --tb=short
        ;;
    "reflector")
        echo -e "${YELLOW}Testing Reflector...${NC}"
        pytest tests/test_reflector.py -v
        ;;
    "learning")
        echo -e "${YELLOW}Testing Learning Hub...${NC}"
        pytest tests/test_learning_hub.py -v
        ;;
    "decision")
        echo -e "${YELLOW}Testing Decision Engine...${NC}"
        pytest tests/test_decision_engine.py -v
        ;;
    "meta")
        echo -e "${YELLOW}Testing Meta-Mind...${NC}"
        pytest tests/test_meta_mind.py -v
        ;;
    "coverage")
        echo -e "${YELLOW}Running tests with coverage...${NC}"
        pytest tests/ --cov=netapi --cov-report=html --cov-report=term
        echo -e "${GREEN}Coverage report generated in htmlcov/index.html${NC}"
        ;;
    "quick")
        echo -e "${YELLOW}Running quick tests (no slow tests)...${NC}"
        pytest tests/ -v -m "not slow"
        ;;
    *)
        echo "Usage: $0 {all|reflector|learning|decision|meta|coverage|quick}"
        exit 1
        ;;
esac

# Check exit code
if [ $? -eq 0 ]; then
    echo -e "\n${GREEN}✅ All tests passed!${NC}"
else
    echo -e "\n${RED}❌ Some tests failed${NC}"
    exit 1
fi
