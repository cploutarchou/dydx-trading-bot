# 🚀 Quick Dev Start Reference

## One-Command Start (Recommended)

```bash
cd /workspaces/dydx-trading-bot
./scripts/dev-start.sh
```

This starts everything automatically:

- ✅ PostgreSQL database
- ✅ Redis cache
- ✅ Backend server (hot-reload)
- ✅ Frontend server (HMR)
- ✅ All health checks
- ✅ Shows all endpoints

**Access after ~30 seconds:**

- Frontend: <http://localhost:5173>
- API: <http://localhost:8000/docs>
- Default login: <admin@example.com> / password

---

## Manual Start (Advanced - 3 Terminals)

### Terminal 1: Database

```bash
cd /workspaces/dydx-trading-bot
docker-compose -f docker-compose.full-stack.yml up postgres redis
```

### Terminal 2: Backend

```bash
cd /workspaces/dydx-trading-bot
python3 -m venv venv
source venv/bin/activate
pip install -r backend/requirements.txt
export PYTHONPATH=/workspaces/dydx-trading-bot:$PYTHONPATH
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

### Terminal 3: Frontend

```bash
cd /workspaces/dydx-trading-bot/frontend
npm install
npm run dev
```

---

## Development Features

### Backend Auto-Reload

- Edit any `.py` file in `backend/` folder
- Server auto-detects changes
- Refresh browser to see changes
- Full error stack traces shown

### Frontend Hot Module Replacement (HMR)

- Edit any `.tsx` or `.css` file in `frontend/src/`
- Changes appear instantly in browser
- Component state is preserved
- No full page reload needed

### API Documentation

- Access: <http://localhost:8000/docs>
- Interactive testing of all endpoints
- Request/response examples
- Auto-generated from Python code

---

## Troubleshooting Quick Fixes

### Backend not starting?

```bash
# Check if port 8000 is in use
lsof -i :8000

# Kill process and restart
kill -9 <PID>
./scripts/dev-start.sh
```

### Frontend not loading?

```bash
# Clear frontend cache
cd /workspaces/dydx-trading-bot/frontend
rm -rf node_modules package-lock.json
npm install
npm run dev
```

### Database connection error?

```bash
# Restart database
docker-compose -f docker-compose.full-stack.yml down -v
docker-compose -f docker-compose.full-stack.yml up postgres redis
```

### Module import errors?

```bash
# Set Python path
export PYTHONPATH=/workspaces/dydx-trading-bot:$PYTHONPATH

# Then restart backend
uvicorn backend.main:app --reload --port 8000
```

---

## Useful Commands

| Task | Command |
|------|---------|
| **Start everything** | `./scripts/dev-start.sh` |
| **Stop all services** | Press `Ctrl+C` |
| **View backend logs** | `docker-compose logs backend` |
| **View database logs** | `docker-compose logs postgres` |
| **Reset database** | `docker-compose down -v` |
| **List running containers** | `docker ps` |
| **Check backend health** | `curl http://localhost:8000/health` |
| **Test API** | `curl http://localhost:8000/docs` |
| **Rebuild frontend** | `cd frontend && npm run build` |

---

## File Structure for Development

```
/workspaces/dydx-trading-bot/
├── backend/
│   ├── main.py              # FastAPI app (edit here)
│   ├── database.py          # SQLAlchemy models
│   ├── auth.py              # Authentication logic
│   ├── services.py          # Business logic
│   └── requirements.txt      # Python dependencies
├── frontend/
│   ├── src/
│   │   ├── App.tsx          # Main component (edit here)
│   │   ├── pages/           # Page components
│   │   ├── store/           # State management
│   │   ├── api.ts           # API client
│   │   └── index.css        # Styles
│   ├── package.json         # Node dependencies
│   ├── vite.config.ts       # Build config
│   └── .env.local           # Frontend config
├── .env                     # Backend config
├── docker-compose.full-stack.yml
└── scripts/
    └── dev-start.sh         # One-command start
```

---

## Making Your First Change

### Backend Change

1. Open `backend/main.py`
2. Find the `/health` endpoint
3. Change response message
4. Save file
5. Refresh <http://localhost:8000/docs>
6. See your change instantly ✨

### Frontend Change

1. Open `frontend/src/pages/Login.tsx`
2. Change button text or styling
3. Save file
4. Page updates automatically in browser ✨
5. No refresh needed!

---

## Full Documentation

For detailed setup and troubleshooting, see: **`DEV_MODE_GUIDE.md`**

For architecture and integration details, see: **`DATABASE_API_IMPLEMENTATION.md`**

---

## Key Ports

| Service | Port | Access |
|---------|------|--------|
| Frontend (Vite) | 5173 | <http://localhost:5173> |
| Backend (FastAPI) | 8000 | <http://localhost:8000> |
| Database (PostgreSQL) | 5432 | localhost:5432 |
| Cache (Redis) | 6379 | localhost:6379 |

---

## Environment Variables

**Backend (.env):**

```
DB_HOST=localhost          # Change if DB on different host
DB_PORT=5432
ENVIRONMENT=development    # Set to "production" for prod
JWT_SECRET_KEY=...        # Change in production!
CORS_ORIGINS=http://localhost:5173,http://localhost:3000
```

**Frontend (.env.local):**

```
VITE_API_URL=http://localhost:8000/api/v1
VITE_WS_URL=ws://localhost:8000
```

---

## Common Workflows

### Debug API Call

1. Go to <http://localhost:8000/docs>
2. Click "Authorize"
3. Login with credentials
4. Click on endpoint
5. Click "Try it out"
6. See request/response

### Add Backend Endpoint

1. Edit `backend/main.py`
2. Add new route with `@app.get()` or `@app.post()`
3. Save file
4. Check <http://localhost:8000/docs> for new endpoint
5. Test immediately in API docs

### Add Frontend Component

1. Create new `.tsx` file in `frontend/src/pages/`
2. Add route in `frontend/src/App.tsx`
3. Save file
4. Navigate to new route in browser
5. Component auto-loads with HMR

---

**Happy coding! 🎉**

For questions, see DEV_MODE_GUIDE.md or DATABASE_API_IMPLEMENTATION.md
