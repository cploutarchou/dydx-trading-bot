#!/bin/bash
# Quick dev container health check script

echo "🔍 Dev Container Health Check"
echo "=============================="

# Check if running in container
if [ -f /.dockerenv ]; then
    echo "✅ Running inside Docker container"
else
    echo "⚠️  Not running in Docker container"
fi

# Check current user
current_user=$(whoami)
echo "👤 Current user: $current_user"

# Check workspace permissions
workspace="/workspaces/dydx-trading-bot"
if [ -d "$workspace" ]; then
    echo "📁 Workspace found: $workspace"
    workspace_owner=$(stat -c '%U' "$workspace")
    echo "🔐 Workspace owner: $workspace_owner"
    
    # Test write permissions
    test_file="$workspace/.health_check_test"
    if touch "$test_file" 2>/dev/null; then
        echo "✅ Write permissions: OK"
        rm -f "$test_file"
    else
        echo "❌ Write permissions: FAILED"
        echo "💡 Run: sudo .devcontainer/fix-permissions.sh $workspace vscode"
    fi
else
    # Fallback to current directory
    workspace=$(pwd)
    echo "📁 Using current directory: $workspace"
    
    # Test write permissions in current directory
    test_file=".health_check_test"
    if touch "$test_file" 2>/dev/null; then
        echo "✅ Write permissions: OK"
        rm -f "$test_file"
    else
        echo "❌ Write permissions: FAILED"
        echo "💡 Run: sudo .devcontainer/fix-permissions.sh $(pwd) vscode"
    fi
fi

# Check Python environment
if command -v python >/dev/null 2>&1; then
    echo "🐍 Python: $(python --version)"
else
    echo "❌ Python: Not found"
fi

# Check VS Code related files
if [ -d ".vscode" ]; then
    echo "🆚 VS Code config: Found"
else
    echo "⚠️  VS Code config: Not found"
fi

echo ""
echo "🎯 Quick fixes if needed:"
echo "   sudo .devcontainer/fix-permissions.sh \$(pwd) vscode"
echo "   su - vscode  # Switch to vscode user"
echo "   code .       # Open in VS Code"