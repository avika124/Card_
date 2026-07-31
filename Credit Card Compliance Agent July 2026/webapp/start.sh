#!/bin/bash
echo ""
echo "  ⚖  ComplyLine — Starting local server..."
echo ""

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "  ERROR: python3 not found."
    echo "  Install it: https://python.org"
    exit 1
fi

# Run server
python3 server.py "$@"
