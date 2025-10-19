#!/bin/bash
# Quick test script to verify backtest flow

set -e

echo "🔧 Backtest System Test"
echo "======================="
echo ""

# Check backend is running
echo "1️⃣  Checking backend availability..."
if curl -s http://localhost:8888/api/v1/users/me > /dev/null 2>&1; then
    echo "✅ Backend is running on port 8888"
else
    echo "❌ Backend not responding. Start with: make backend-run"
    exit 1
fi

# Check database connection
echo ""
echo "2️⃣  Checking database connection..."
python3 -c "
from backend.database import SessionLocal, BacktestRun
try:
    db = SessionLocal()
    count = db.query(BacktestRun).count()
    print(f'✅ Database connected ({count} backtests recorded)')
except Exception as e:
    print(f'❌ Database error: {e}')
    exit(1)
" || exit 1

# Check recent backtest status
echo ""
echo "3️⃣  Recent backtest runs:"
python3 -c "
from backend.database import SessionLocal, BacktestRun
db = SessionLocal()
runs = db.query(BacktestRun).order_by(BacktestRun.id.desc()).limit(3).all()
if not runs:
    print('   (No backtests yet)')
else:
    for run in runs:
        print(f'   - {run.run_id[:8]}... Status: {run.status:12} Created: {run.created_at}')
"

echo ""
echo "4️⃣  Frontend check:"
if curl -s http://localhost:5173 > /dev/null 2>&1; then
    echo "✅ Frontend is running on port 5173"
else
    echo "ℹ️  Frontend not running (optional)"
fi

echo ""
echo "✅ System check complete!"
echo ""
echo "📝 Next steps:"
echo "1. Go to http://localhost:5173"
echo "2. Click 'Run Backtest'"
echo "3. Watch backend logs for [Backtest xxx] messages"
echo "4. Status should update to 'completed' in database"
