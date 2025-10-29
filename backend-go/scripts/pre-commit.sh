#!/bin/bash
# Pre-commit hook for Go projects
# Copy this to .git/hooks/pre-commit and make it executable:
# cp scripts/pre-commit.sh .git/hooks/pre-commit
# chmod +x .git/hooks/pre-commit

set -e

echo "🔍 Running pre-commit checks..."

# Format check
echo "📝 Checking code formatting..."
UNFORMATTED=$(gofmt -l .)
if [ -n "$UNFORMATTED" ]; then
    echo "❌ The following files are not formatted:"
    echo "$UNFORMATTED"
    echo "Run: make fmt"
    exit 1
fi
echo "✅ Code formatting OK"

# Go vet
echo "🔎 Running go vet..."
if ! go vet ./...; then
    echo "❌ go vet failed"
    exit 1
fi
echo "✅ go vet OK"

# Linting (if golangci-lint is available)
if command -v golangci-lint > /dev/null; then
    echo "🔍 Running linter..."
    if ! golangci-lint run --config .golangci.yml ./...; then
        echo "❌ Linting failed"
        echo "Run: make lint-fix to auto-fix issues"
        exit 1
    fi
    echo "✅ Linting OK"
else
    echo "⚠️  golangci-lint not found, skipping lint checks"
    echo "Install with: make install-tools"
fi

# Run tests
echo "🧪 Running tests..."
if ! go test -short ./...; then
    echo "❌ Tests failed"
    exit 1
fi
echo "✅ Tests OK"

echo "✅ All pre-commit checks passed!"
exit 0

