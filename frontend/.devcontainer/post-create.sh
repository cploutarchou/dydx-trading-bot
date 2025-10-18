#!/bin/bash

# DevContainer post-create script to install any missing global packages
echo "🔧 Setting up development tools..."

# Function to check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Install missing global packages
packages=("pnpm" "yarn" "tsx" "ts-node" "nodemon")

for package in "${packages[@]}"; do
    if ! command_exists "$package"; then
        echo "📦 Installing $package..."
        npm install -g "$package" || echo "⚠️ Failed to install $package"
    else
        echo "✅ $package is already installed"
    fi
done

# Verify installation
echo ""
echo "🔍 Checking installed tools:"
for package in "${packages[@]}"; do
    if command_exists "$package"; then
        echo "✅ $package: $(command -v "$package")"
    else
        echo "❌ $package: not found"
    fi
done

echo ""
echo "🎉 Development environment setup complete!"
echo "💡 You can run 'npm run dev' to start the development server"