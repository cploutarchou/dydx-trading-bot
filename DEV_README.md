# 🚀 Development Mode - Quick Start

## One Command to Start Everything

```bash
cd /workspaces/dydx-trading-bot && ./scripts/dev-start.sh
```

That's all you need! This starts:

- ✅ PostgreSQL Database (port 5432)
- ✅ Redis Cache (port 6379)
- ✅ Backend API (port 8000) with **auto-reload**
- ✅ Frontend UI (port 5173) with **hot-reload**

Takes about **30 seconds** to fully start.

---

## Access Your Application

After running `./scripts/dev-start.sh`:

| Component | URL | Purpose |
|-----------|-----|---------|
| **Frontend** | <http://localhost:5173> | React application |
| **API Docs** | <http://localhost:8000/docs> | Test API endpoints |
| **Backend API** | <http://localhost:8000> | API server |

---

## Login

Use these credentials:

```
Email:    admin@example.com
Password: password
```

Or register a new account on the login page.

---

## Making Changes (The Magic!)

### Edit Backend Code

1. Edit any file in `backend/` folder
2. Save the file (Ctrl+S)
3. Server automatically restarts (~1 second)
4. Refresh browser to see changes

Example: Edit `backend/main.py` and save

### Edit Frontend Code

1. Edit any file in `frontend/src/` folder
2. Save the file (Ctrl+S)
3. Browser **automatically updates** (~100ms) - **No refresh needed!**
4. Component state is preserved

Example: Edit `frontend/src/pages/Login.tsx` and save

---

## If You Want Manual Control (3 Terminals)

### Terminal 1 - Database

```bash
docker-compose -f docker-compose.full-stack.yml up postgres redis
```

### Terminal 2 - Backend

```bash
cd /workspaces/dydx-trading-bot
python3 -m venv venv
source venv/bin/activate
pip install -r backend/requirements.txt
export PYTHONPATH=/workspaces/dydx-trading-bot:$PYTHONPATH
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

### Terminal 3 - Frontend

```bash
cd /workspaces/dydx-trading-bot/frontend
npm install
npm run dev
```

---

## Common Issues & Fixes

### Port Already in Use

```bash
lsof -i :8000
kill -9 <PID>
./scripts/dev-start.sh
```

### Database Connection Error

```bash
docker-compose -f docker-compose.full-stack.yml down -v
docker-compose -f docker-compose.full-stack.yml up postgres redis
```

### Backend Module Import Error

```bash
export PYTHONPATH=/workspaces/dydx-trading-bot:$PYTHONPATH
```

### Frontend Dependencies Error

```bash
cd /workspaces/dydx-trading-bot/frontend
rm -rf node_modules package-lock.json
npm install
npm run dev
```

---

## Documentation

- **Complete Guide**: `DEV_MODE_GUIDE.md` (200+ lines)
- **Quick Reference**: `DEV_QUICK_START.md`
- **Architecture**: `DATABASE_API_IMPLEMENTATION.md`

---

## Developer Features Enabled

✨ **Backend**

- Auto-reload on file changes
- Full debug logging
- Interactive API docs (/docs)
- Complete error stack traces

✨ **Frontend**

- Hot Module Replacement (HMR)
- Instant component updates
- No page refreshes needed
- Component state preserved

✨ **Database**

- PostgreSQL with persistent data
- Redis caching
- Auto-setup on first run

---

## Workflow Example

1. Start dev environment:

   ```bash
   ./scripts/dev-start.sh
   ```

2. Open browser: <http://localhost:5173>

3. Edit `frontend/src/pages/Login.tsx`
   - Change button text
   - Save file
   - See changes **instantly** in browser! 🎉

4. Edit `backend/main.py`
   - Change an endpoint
   - Save file
   - Backend restarts automatically
   - Test at <http://localhost:8000/docs>

---

## Stop Everything

Press `Ctrl+C` in the terminal running `./scripts/dev-start.sh`

---

## Useful Commands

| Task | Command |
|------|---------|
| Check backend health | `curl http://localhost:8000/health` |
| View container logs | `docker-compose logs -f backend` |
| Reset database | `docker-compose down -v` |
| Stop all services | `Ctrl+C` (in terminal) |
| Restart backend only | `docker-compose restart backend` |

---

## Happy Coding! 🚀

Everything is ready for development. Just run:

```bash
./scripts/dev-start.sh
```

Then start editing and see your changes instantly!
