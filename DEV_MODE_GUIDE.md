# 🚀 Development Mode Guide - Running Backend & Frontend Locally

This guide shows how to run the backend and frontend in development mode on the dev container with hot-reload support.

## Table of Contents

1. [Quick Start (TL;DR)](#quick-start)
2. [Backend Setup](#backend-setup)
3. [Frontend Setup](#frontend-setup)
4. [Running Both Simultaneously](#running-both-simultaneously)
5. [Troubleshooting](#troubleshooting)

---

## Quick Start (TL;DR)

**If you just want to get it running:**

### Terminal 1: Start Database & Redis

```bash
cd /workspaces/dydx-trading-bot
docker-compose -f docker-compose.full-stack.yml up postgres redis
```

### Terminal 2: Backend (Python)

```bash
cd /workspaces/dydx-trading-bot
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r backend/requirements.txt
export PYTHONPATH=/workspaces/dydx-trading-bot:$PYTHONPATH
cd backend
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Terminal 3: Frontend (Node.js)

```bash
cd /workspaces/dydx-trading-bot/frontend
npm install
npm run dev
```

Then access:

- **Frontend**: <http://localhost:5173>
- **Backend API**: <http://localhost:8000>
- **API Docs**: <http://localhost:8000/docs>

---

## Backend Setup

### Step 1: Install Python Dependencies

```bash
cd /workspaces/dydx-trading-bot

# Create virtual environment (optional but recommended)
python3 -m venv venv
source venv/bin/activate

# Install backend dependencies
pip install -r backend/requirements.txt
```

### Step 2: Set Up Environment Variables

Create `.env` file in project root:

```bash
cat > /workspaces/dydx-trading-bot/.env << 'EOF'
# Database Configuration
DB_TYPE=postgresql
DB_NAME=dydx_backtest
DB_USER=postgres
DB_PASSWORD=password
DB_HOST=localhost
DB_PORT=5432

# JWT Configuration
JWT_SECRET_KEY=your-secret-key-change-in-production-use-strong-key-32-chars-minimum
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7

# Server Configuration
ENVIRONMENT=development
CORS_ORIGINS=http://localhost:3000,http://localhost:5173,http://localhost:8000

# API Configuration
SQL_ECHO=false
EOF
```

### Step 3: Start PostgreSQL & Redis (Docker)

In a separate terminal, start the database and cache:

```bash
cd /workspaces/dydx-trading-bot
docker-compose -f docker-compose.full-stack.yml up postgres redis
```

**Output should show:**

```
postgres_1  | LOG:  database system is ready to accept connections
redis_1     | * Ready to accept connections
```

### Step 4: Run Backend with Hot-Reload

```bash
cd /workspaces/dydx-trading-bot

# Ensure virtual environment is active
source venv/bin/activate

# Set Python path
export PYTHONPATH=/workspaces/dydx-trading-bot:$PYTHONPATH

# Run backend with auto-reload
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000 --log-level debug
```

**Expected Output:**

```
INFO:     Started server process [12345]
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
INFO:     Will watch for changes in these directories: ['/workspaces/dydx-trading-bot']
```

### Backend Dev Mode Features

✅ **Auto-reload**: Changes to Python files automatically restart the server
✅ **Debug logging**: Full request/response logging
✅ **Interactive API docs**: <http://localhost:8000/docs>
✅ **Error stack traces**: Full error details in console and browser

---

## Frontend Setup

### Step 1: Install Node Dependencies

```bash
cd /workspaces/dydx-trading-bot/frontend

# Install dependencies
npm install

# OR with yarn
yarn install
```

### Step 2: Set Up Environment Variables

Create `frontend/.env.local`:

```bash
cat > /workspaces/dydx-trading-bot/frontend/.env.local << 'EOF'
VITE_API_URL=http://localhost:8000/api/v1
VITE_WS_URL=ws://localhost:8000
EOF
```

### Step 3: Run Frontend with Dev Server

```bash
cd /workspaces/dydx-trading-bot/frontend

# Start Vite dev server with hot reload
npm run dev
```

**Expected Output:**

```
  VITE v5.0.0  ready in 234 ms

  ➜  Local:   http://localhost:5173/
  ➜  press h to show help
```

### Frontend Dev Mode Features

✅ **Hot Module Replacement (HMR)**: Instant updates without full reload
✅ **Fast Refresh**: React component changes appear instantly
✅ **Source maps**: Debug with original TypeScript code
✅ **Error overlay**: Display compilation errors in browser

---

## Running Both Simultaneously

### Option A: Using VS Code Terminal Groups (Recommended)

1. **Create 3 terminals** in VS Code:
   - Terminal 1: Database
   - Terminal 2: Backend
   - Terminal 3: Frontend

2. **Terminal 1 - Database & Redis:**

```bash
cd /workspaces/dydx-trading-bot
docker-compose -f docker-compose.full-stack.yml up postgres redis
```

3. **Terminal 2 - Backend:**

```bash
cd /workspaces/dydx-trading-bot
source venv/bin/activate
export PYTHONPATH=/workspaces/dydx-trading-bot:$PYTHONPATH
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000 --log-level debug
```

4. **Terminal 3 - Frontend:**

```bash
cd /workspaces/dydx-trading-bot/frontend
npm run dev
```

### Option B: Using tmux (Advanced)

Create a tmux session with all 3 services:

```bash
#!/bin/bash

# Create new tmux session
tmux new-session -d -s dydx -x 200 -y 50

# Window 0: Database
tmux send-keys -t dydx "cd /workspaces/dydx-trading-bot && docker-compose -f docker-compose.full-stack.yml up postgres redis" Enter
tmux new-window -t dydx -n backend

# Window 1: Backend
tmux send-keys -t dydx:backend "cd /workspaces/dydx-trading-bot && source venv/bin/activate && export PYTHONPATH=/workspaces/dydx-trading-bot:\$PYTHONPATH && uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000" Enter
tmux new-window -t dydx -n frontend

# Window 2: Frontend
tmux send-keys -t dydx:frontend "cd /workspaces/dydx-trading-bot/frontend && npm run dev" Enter

# Attach to the session
tmux attach -t dydx
```

Save as `start_dev.sh` and run:

```bash
chmod +x start_dev.sh
./start_dev.sh
```

### Option C: Using Shell Script

Create `scripts/dev-start.sh`:

```bash
#!/bin/bash

echo "🚀 Starting dYdX Trading Bot in Development Mode"
echo "================================================="
echo ""

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

# Check if PostgreSQL is accessible
check_postgres() {
    echo "${BLUE}Checking PostgreSQL...${NC}"
    if docker ps | grep -q dydx_backtest_db; then
        echo "✓ PostgreSQL already running"
    else
        echo "Starting PostgreSQL and Redis..."
        docker-compose -f docker-compose.full-stack.yml up -d postgres redis
        sleep 5
        echo "✓ PostgreSQL and Redis started"
    fi
}

# Start backend
start_backend() {
    echo ""
    echo "${BLUE}Starting Backend...${NC}"
    cd /workspaces/dydx-trading-bot
    source venv/bin/activate 2>/dev/null || python3 -m venv venv && source venv/bin/activate
    pip install -r backend/requirements.txt > /dev/null 2>&1
    export PYTHONPATH=/workspaces/dydx-trading-bot:$PYTHONPATH
    cd backend
    uvicorn main:app --reload --host 0.0.0.0 --port 8000 --log-level debug &
    BACKEND_PID=$!
    echo "✓ Backend running (PID: $BACKEND_PID)"
}

# Start frontend
start_frontend() {
    echo ""
    echo "${BLUE}Starting Frontend...${NC}"
    cd /workspaces/dydx-trading-bot/frontend
    npm install > /dev/null 2>&1
    npm run dev &
    FRONTEND_PID=$!
    echo "✓ Frontend running (PID: $FRONTEND_PID)"
}

# Show info
show_info() {
    echo ""
    echo "${GREEN}✅ Development Environment Ready!${NC}"
    echo ""
    echo "Endpoints:"
    echo "  🌐 Frontend:   ${GREEN}http://localhost:5173${NC}"
    echo "  🔌 Backend:    ${GREEN}http://localhost:8000${NC}"
    echo "  📚 API Docs:   ${GREEN}http://localhost:8000/docs${NC}"
    echo ""
    echo "PIDs:"
    echo "  Backend:  $BACKEND_PID"
    echo "  Frontend: $FRONTEND_PID"
    echo ""
    echo "To stop all services:"
    echo "  kill $BACKEND_PID $FRONTEND_PID"
    echo "  docker-compose -f docker-compose.full-stack.yml down"
    echo ""
}

# Main
check_postgres
start_backend
start_frontend
show_info

# Keep script running
wait
```

---

## Accessing the Application

### Frontend

- **URL**: <http://localhost:5173>
- **Hot Reload**: Enabled (changes appear instantly)

### Backend API

- **URL**: <http://localhost:8000>
- **Interactive Docs**: <http://localhost:8000/docs>
- **Auto-reload**: Enabled (changes restart server)

### Test Login

```
Email: admin@example.com
Password: password
```

Or register a new account at the login page.

---

## Development Workflow

### Making Changes

#### Python Backend Changes

1. Edit any file in `backend/` folder
2. Save the file
3. Uvicorn automatically detects changes and reloads
4. Refresh API browser or test endpoint

#### React Frontend Changes

1. Edit any file in `frontend/src/` folder
2. Save the file
3. Vite automatically hot-reloads the page
4. See changes instantly in browser

### Testing the API

**Using cURL:**

```bash
# Register user
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"password123"}'

# Login
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"password123"}'

# Get current user (use token from login response)
curl -X GET http://localhost:8000/api/v1/users/me \
  -H "Authorization: Bearer YOUR_TOKEN_HERE"
```

**Using Interactive Docs:**

1. Navigate to <http://localhost:8000/docs>
2. Click "Authorize" button
3. Use credentials to login
4. Test all endpoints directly in browser

---

## Troubleshooting

### PostgreSQL Connection Error

```
ERROR: could not connect to server: Connection refused
```

**Fix:**

```bash
# Check if container is running
docker ps | grep postgres

# If not running, start it
docker-compose -f docker-compose.full-stack.yml up postgres redis

# Or reset database
docker-compose -f docker-compose.full-stack.yml down -v
docker-compose -f docker-compose.full-stack.yml up postgres redis
```

### Port Already in Use

```
ERROR: [Errno 98] Address already in use
```

**Fix:**

```bash
# Find process using port 8000
lsof -i :8000

# Kill it
kill -9 <PID>

# Or use different port
uvicorn backend.main:app --reload --port 8001
```

### Node Dependencies Error

```
npm ERR! Could not resolve dependency
```

**Fix:**

```bash
cd /workspaces/dydx-trading-bot/frontend
rm -rf node_modules package-lock.json
npm install
```

### Backend Module Not Found

```
ModuleNotFoundError: No module named 'backend'
```

**Fix:**

```bash
# Set Python path before running
export PYTHONPATH=/workspaces/dydx-trading-bot:$PYTHONPATH

# Then run uvicorn from project root
cd /workspaces/dydx-trading-bot
uvicorn backend.main:app --reload --port 8000
```

### Cannot Connect to Backend from Frontend

```
GET http://localhost:8000/api/v1/users/me 404 (Not Found)
```

**Fix:**

1. Check backend is running: `curl http://localhost:8000/health`
2. Check CORS origins in `.env`:

   ```
   CORS_ORIGINS=http://localhost:3000,http://localhost:5173,http://localhost:8000
   ```

3. Verify frontend .env:

   ```
   VITE_API_URL=http://localhost:8000/api/v1
   ```

---

## Performance Tips

### Backend

- Use `--log-level info` instead of `--log-level debug` for less logging overhead
- Monitor database queries with `SQL_ECHO=true` in `.env`
- Check memory with: `top` (press `Shift+M` to sort by memory)

### Frontend

- Use React Developer Tools browser extension for component profiling
- Check network requests in browser DevTools (F12)
- Monitor build time: `npm run build` to check production size

---

## Next Steps

1. **Make changes** to backend/frontend code
2. **Watch hot-reload** in action
3. **Test your changes** in browser or API docs
4. **Debug** using browser DevTools and Python logging
5. **Commit changes** when ready to git

Happy coding! 🎉
