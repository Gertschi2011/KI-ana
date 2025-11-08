#!/bin/bash
cd /home/kiana/ki_ana

# Kill old processes
sudo pkill -f "uvicorn netapi.app" 2>/dev/null

# Wait
sleep 2

# Start with system python and installed packages
export PYTHONPATH=/home/kiana/ki_ana:$PYTHONPATH
nohup /home/kiana/.local/bin/uvicorn netapi.app:app --host 0.0.0.0 --port 8000 --log-level info > /tmp/backend.log 2>&1 &

echo "Backend starting... check /tmp/backend.log"
sleep 3

# Check if running
if ss -tlnp | grep -q ":8000"; then
    echo "✅ Backend is running on port 8000"
else
    echo "❌ Backend failed to start. Check /tmp/backend.log"
    tail -20 /tmp/backend.log
fi
