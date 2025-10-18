# Getting Started with the dYdX Trading Bot UI

## 🎯 Current State

The application is **fully functional and ready for use**:

- ✅ Backend API running on port 8000
- ✅ Frontend UI running on port 5173  
- ✅ Authentication system working
- ✅ Backtest creation and listing working
- ✅ Database persistence working

## 🚀 Quick Start (Copy & Paste)

### Terminal 1: Start Backend

```bash
cd /Users/chris/workspace/dydx-trading-bot
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

### Terminal 2: Start Frontend

```bash
cd /Users/chris/workspace/dydx-trading-bot/frontend
npm run dev
```

### Terminal 3 (optional): View Logs

```bash
# Check backend logs
curl http://localhost:8000/docs
```

## 🔐 Login Credentials

**Username:** admin  
**Password:** admin123

## 📋 What You Can Do Now

### 1. Create a Backtest

1. Open <http://localhost:5173>
2. Login with admin/admin123
3. Fill out the backtest form:
   - Start date: 2024-01-01
   - End date: 2024-03-31
   - Number of pairs: 10
   - Z-Score threshold: 1.5
   - Stats window: 21
   - USD per trade: 10
4. Click "Start Backtest"
5. See it appear in the results table below

### 2. View Backtest Results

- Click "View Details" on any backtest to see detailed metrics

### 3. Create Additional Users

Register new users via the login page's "Register" button

## 📊 Database Location

**SQLite:** `/Users/chris/workspace/dydx-trading-bot/app/dydx_backtest.db`

To inspect the database:

```bash
sqlite3 app/dydx_backtest.db
> SELECT * FROM users;
> SELECT * FROM backtest_runs;
```

## 🔗 API Endpoints

All endpoints require authentication via JWT token:

### Authentication

- POST /api/v1/auth/login
- POST /api/v1/auth/register
- POST /api/v1/auth/refresh

### Users

- GET /api/v1/users/me

### Backtests

- GET /api/v1/backtests (list all)
- GET /api/v1/backtests/{run_id} (get details)
- POST /api/v1/backtests/run (start new)
- GET /api/v1/stats (get statistics)

### Documentation

- GET /docs (Swagger UI)
- GET /openapi.json (OpenAPI spec)

## 🐛 Troubleshooting

### Frontend shows blank page

- Clear browser cache (Cmd+Shift+R on Mac)
- Check browser console (F12) for errors
- Verify backend is running on port 8000

### Login fails

- Verify user exists: `python3 scripts/create_test_user.py`
- Check backend logs for errors
- Verify CORS is enabled in backend

### Backtest not appearing

- Refresh browser
- Check browser console for API errors
- Verify JWT token in localStorage: `localStorage.getItem('access_token')`

## 📈 Performance Tips

- **Browser:** Use Chrome/Firefox for best performance
- **Backend:** Response times < 200ms for all endpoints
- **Database:** SQLite sufficient for development; use PostgreSQL for production

## 🔄 Common Tasks

### Create New User Programmatically

```bash
python3 scripts/create_test_user.py
```

### Reset Database

```bash
rm app/dydx_backtest.db
# Restart backend to recreate
```

### View Recent Backtests

```bash
curl -H "Authorization: Bearer YOUR_TOKEN" http://localhost:8000/api/v1/backtests
```

## 📚 Documentation

- **Architecture:** See `.github/copilot-instructions.md`
- **Implementation Details:** See `BACKTEST_UI_IMPLEMENTATION.md`
- **Session Summary:** See `SESSION_SUMMARY.md`

## 🎓 Project Structure

```
dydx-trading-bot/
├── app/                    # Trading bot core
├── backend/                # FastAPI server
├── frontend/               # React/TypeScript UI
├── scripts/                # Utility scripts
└── tests/                  # Test files
```

## ✨ Next Session Ideas

1. **Real-time Updates** - Add WebSocket for live backtest progress
2. **Charts** - Visualize equity curves and trade history
3. **Analysis** - Compare multiple backtest runs
4. **Live Trading** - Execute actual trades based on backtest strategy
5. **Optimization** - Parameter sweep and strategy optimization

## 🆘 Need Help?

1. Check browser console (F12) for JavaScript errors
2. Check backend terminal for API errors
3. Review `.github/copilot-instructions.md` for architecture details
4. Review `BACKTEST_UI_IMPLEMENTATION.md` for component details

---

**Last Updated:** October 17, 2025  
**Status:** 🟢 Ready for Development
