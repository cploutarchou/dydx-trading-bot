#!/bin/bash
# Fix permissions for dev container file access

set -e

WORKSPACE_PATH="${1:-/workspaces/dydx-trading-bot}"
USER="${2:-vscode}"

echo "🔧 Fixing permissions for dev container..."
echo "   Workspace: $WORKSPACE_PATH"
echo "   User: $USER"

# Create user if it doesn't exist
if ! id "$USER" &>/dev/null; then
    echo "Creating user: $USER"
    useradd -m -s /bin/bash "$USER"
fi

# Get user ID and group ID
USER_ID=$(id -u "$USER")
GROUP_ID=$(id -g "$USER")

echo "   User ID: $USER_ID"
echo "   Group ID: $GROUP_ID"

# Fix ownership of the workspace
if [ -d "$WORKSPACE_PATH" ]; then
    echo "Changing ownership of $WORKSPACE_PATH to $USER:$USER..."
    chown -R "$USER_ID:$GROUP_ID" "$WORKSPACE_PATH"
    
    # Set proper permissions for files and directories
    echo "Setting proper permissions..."
    find "$WORKSPACE_PATH" -type d -exec chmod 755 {} \;
    find "$WORKSPACE_PATH" -type f -exec chmod 644 {} \;
    
    # Make scripts executable
    if [ -d "$WORKSPACE_PATH/scripts" ]; then
        echo "Making scripts executable..."
        find "$WORKSPACE_PATH/scripts" -name "*.py" -exec chmod +x {} \;
        find "$WORKSPACE_PATH/scripts" -name "*.sh" -exec chmod +x {} \;
    fi
    
    # Make setup scripts executable
    if [ -f "$WORKSPACE_PATH/.devcontainer/setup.sh" ]; then
        chmod +x "$WORKSPACE_PATH/.devcontainer/setup.sh"
    fi
    
    if [ -f "$WORKSPACE_PATH/.devcontainer/fix-permissions.sh" ]; then
        chmod +x "$WORKSPACE_PATH/.devcontainer/fix-permissions.sh"
    fi
    
    echo "✅ Permissions fixed successfully!"
else
    echo "❌ Workspace path $WORKSPACE_PATH not found!"
    exit 1
fi

# Fix git permissions if .git exists
if [ -d "$WORKSPACE_PATH/.git" ]; then
    echo "Fixing git permissions..."
    chown -R "$USER_ID:$GROUP_ID" "$WORKSPACE_PATH/.git"
fi

echo "🎉 Dev container permissions setup complete!"