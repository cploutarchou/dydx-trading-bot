#!/bin/bash
# DevContainer Setup Script
# This script sets up the development environment inside the DevContainer

set -e

echo "🚀 Setting up dYdX Trading Bot Frontend DevContainer..."

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if running inside DevContainer
if [ -z "$CONTAINER_NAME" ]; then
    echo "⚠️  Warning: This script should be run inside the DevContainer"
fi

echo -e "${BLUE}📦 Installing dependencies...${NC}"
npm install

echo -e "${BLUE}🏗️  Building the project...${NC}"
npm run build

# Create .env file if it doesn't exist
if [ ! -f ".env.local" ]; then
    echo -e "${BLUE}📝 Creating .env.local...${NC}"
    cat > .env.local << EOF
VITE_API_URL=http://localhost:8000
NODE_ENV=development
EOF
    echo -e "${GREEN}✅ .env.local created${NC}"
fi

# Create git hooks directory
mkdir -p .git/hooks

# Create pre-commit hook for linting
cat > .git/hooks/pre-commit << 'HOOK_EOF'
#!/bin/bash
echo "🔍 Running pre-commit checks..."
npm run lint
HOOK_EOF

chmod +x .git/hooks/pre-commit

echo -e "${GREEN}✅ DevContainer setup complete!${NC}"
echo ""
echo -e "${YELLOW}📚 Next steps:${NC}"
echo "1. Start the development server: npm run dev"
echo "2. Access the app at: http://localhost:5173"
echo "3. Backend API is at: http://localhost:8000"
echo ""
echo -e "${YELLOW}💡 Available commands:${NC}"
echo "  - npm run dev      : Start dev server"
echo "  - npm run build    : Build for production"
echo "  - npm run lint     : Run linter"
echo "  - npm run preview  : Preview production build"
