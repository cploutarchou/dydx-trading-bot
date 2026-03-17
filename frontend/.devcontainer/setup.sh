#!/bin/bash
# DevContainer Setup Script
# Sets up the development environment inside the DevContainer

set -euo pipefail

echo "🚀 Setting up dYdX Trading Bot Frontend DevContainer..."

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if running inside DevContainer
if [ -z "${CONTAINER_NAME:-}" ]; then
    echo "⚠️  Warning: This script should be run inside the DevContainer"
fi

echo -e "${BLUE}📦 Installing dependencies...${NC}"
if ! [ -d node_modules ]; then
    npm ci || npm install
else
    echo -e "${YELLOW}Dependencies already present, skipping install${NC}"
fi

echo -e "${BLUE}🏗️  Building the project...${NC}"
if npm run build 2>&1 | head -20; then
    echo -e "${GREEN}✅ Build completed${NC}"
else
    echo -e "${YELLOW}⚠ Build encountered issues (may be acceptable initially)${NC}"
fi

# Create .env file if it doesn't exist
if [ ! -f ".env.local" ]; then
    echo -e "${BLUE}📝 Creating .env.local...${NC}"
    cat > .env.local << EOF
VITE_API_URL=http://localhost:8889
NODE_ENV=development
EOF
    echo -e "${GREEN}✅ .env.local created${NC}"
else
    echo -e "${YELLOW}⚠ .env.local already exists, skipping${NC}"
fi

# Create git hooks directory
mkdir -p .git/hooks

# Create pre-commit hook for linting
cat > .git/hooks/pre-commit << 'HOOK_EOF'
#!/bin/bash
echo "🔍 Running pre-commit checks..."
STAGED=$(git diff --cached --name-only --diff-filter=ACM | grep -E '\.(ts|tsx|js|jsx)$')
if [ -n "$STAGED" ]; then
    npm run lint -- $STAGED || exit 1
fi
HOOK_EOF

chmod +x .git/hooks/pre-commit

echo -e "${GREEN}✅ DevContainer setup complete!${NC}"
echo ""
echo -e "${YELLOW}📚 Next steps:${NC}"
echo "1. Start the development server: npm run dev"
echo "2. Access the app at: http://localhost:5173"
echo "3. Backend API is at: http://localhost:8889"
echo ""
echo -e "${YELLOW}💡 Available commands:${NC}"
echo "  - npm run dev      : Start dev server"
echo "  - npm run build    : Build for production"
echo "  - npm run lint     : Run linter"
echo "  - npm run preview  : Preview production build"
