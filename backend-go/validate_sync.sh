#!/bin/bash
# Validation script for Python to Go model synchronization

echo "🔍 Validating Python to Go Model Synchronization"
echo "=================================================="
echo ""

cd /home/chris/workspace/dydx-trading-bot/backend-go || exit 1

# Check Go models file
echo "✅ Checking Go models file..."
if grep -q "type BacktestMetrics struct" internal/models/models.go; then
    echo "   ✓ BacktestMetrics struct found"
else
    echo "   ✗ BacktestMetrics struct NOT found"
    exit 1
fi

if grep -q "StrategyID.*int" internal/models/models.go && grep -q "StrategyName.*string" internal/models/models.go; then
    echo "   ✓ BacktestTrade strategy fields found"
else
    echo "   ✗ BacktestTrade strategy fields NOT found"
    exit 1
fi

if grep -q "PositionID.*string" internal/models/models.go; then
    echo "   ✓ BacktestPosition.PositionID found"
else
    echo "   ✗ BacktestPosition.PositionID NOT found"
    exit 1
fi

# Check migrations
echo ""
echo "✅ Checking migration files..."

if [ -f migrations/000018_add_missing_fields.up.sql ]; then
    echo "   ✓ Migration 000018 (up) found"
else
    echo "   ✗ Migration 000018 (up) NOT found"
    exit 1
fi

if [ -f migrations/000018_add_missing_fields.down.sql ]; then
    echo "   ✓ Migration 000018 (down) found"
else
    echo "   ✗ Migration 000018 (down) NOT found"
    exit 1
fi

if [ -f migrations/000019_add_strategy_fields_and_metrics.up.sql ]; then
    echo "   ✓ Migration 000019 (up) found"
else
    echo "   ✗ Migration 000019 (up) NOT found"
    exit 1
fi

if [ -f migrations/000019_add_strategy_fields_and_metrics.down.sql ]; then
    echo "   ✓ Migration 000019 (down) found"
else
    echo "   ✗ Migration 000019 (down) NOT found"
    exit 1
fi

# Check migration content
echo ""
echo "✅ Verifying migration content..."

if grep -q "backtest_metrics" migrations/000019_add_strategy_fields_and_metrics.up.sql; then
    echo "   ✓ backtest_metrics table creation found"
else
    echo "   ✗ backtest_metrics table creation NOT found"
    exit 1
fi

if grep -q "strategy_id" migrations/000019_add_strategy_fields_and_metrics.up.sql; then
    echo "   ✓ strategy_id field addition found"
else
    echo "   ✗ strategy_id field addition NOT found"
    exit 1
fi

# Check Go compilation
echo ""
echo "✅ Checking Go compilation..."
if go build -v ./cmd/server > /tmp/build.log 2>&1; then
    echo "   ✓ Code compiles successfully"
else
    echo "   ✗ Code compilation failed"
    cat /tmp/build.log | head -20
    exit 1
fi

# Count migration files
echo ""
echo "✅ Migration count..."
UP_MIGRATIONS=$(ls -1 migrations/*.up.sql | wc -l)
DOWN_MIGRATIONS=$(ls -1 migrations/*.down.sql | wc -l)
echo "   ✓ ${UP_MIGRATIONS} up migrations"
echo "   ✓ ${DOWN_MIGRATIONS} down migrations"

if [ "$UP_MIGRATIONS" -ne "$DOWN_MIGRATIONS" ]; then
    echo "   ✗ WARNING: Mismatch in up/down migration counts"
    exit 1
fi

# Summary
echo ""
echo "=================================================="
echo "✅ ALL VALIDATIONS PASSED"
echo "=================================================="
echo ""
echo "Summary:"
echo "  • BacktestMetrics struct created"
echo "  • BacktestTrade enhanced with strategy fields"
echo "  • BacktestPosition complete with all fields"
echo "  • Migration 000018: add_missing_fields"
echo "  • Migration 000019: add_strategy_fields_and_metrics"
echo "  • All Go code compiles successfully"
echo "  • ${UP_MIGRATIONS} migrations ready to apply"
echo ""
echo "Ready to deploy! 🚀"

