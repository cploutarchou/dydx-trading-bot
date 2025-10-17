# Database & API Integration Guide

Complete guide for integrating backtest results storage, REST API, WebSocket updates, and React UI dashboard.

## 📋 Architecture Overview

```
Frontend (React + Vite)
    ↓ (HTTPS/WSS)
    ├→ REST API (FastAPI)
    │   ├→ PostgreSQL (backtest results storage)
    │   └→ Redis (caching/sessions)
    └→ WebSocket (real-time updates)
```

## 🗂️ Project Structure

```
backend/
├── __init__.py              # Package initialization
├── main.py                  # FastAPI server + WebSocket endpoints
├── database.py              # SQLAlchemy models & DB config
├── auth.py                  # JWT authentication
├── services.py              # Business logic & CRUD operations
└── requirements.txt         # Backend dependencies

frontend/
├── package.json             # Node dependencies & scripts
├── vite.config.ts          # Vite configuration
├── src/
│   ├── App.tsx             # Main app component
│   ├── main.tsx            # React entry point
│   ├── index.css           # Tailwind CSS styles
│   ├── api.ts              # API client with axios
│   ├── store/
│   │   └── auth.ts         # Zustand auth store
│   └── pages/
│       ├── Login.tsx       # Login page
│       └── BacktestDetails.tsx  # Backtest details page
├── Dockerfile              # Production image
└── Dockerfile.dev          # Development image

docker-compose.full-stack.yml   # Full stack orchestration
backend.Dockerfile             # Backend container
```

## 🚀 Quick Start

### Option 1: Docker Compose (Recommended)

```bash
# Start full stack (backend + frontend + database)
docker-compose -f docker-compose.full-stack.yml up -d

# Access the application
# Frontend: http://localhost:3000 (or http://localhost:5173 for dev)
# API: http://localhost:8000
# API Docs: http://localhost:8000/docs
# Database: postgres://postgres:password@localhost:5432/dydx_backtest
```

### Option 2: Local Development

**Prerequisites:**
- Python 3.11+
- Node.js 18+
- PostgreSQL 15+ (or SQLite for dev)

**Backend Setup:**

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows

# Install backend dependencies
pip install -r backend/requirements.txt

# Initialize database
python -c "from backend.database import init_db; init_db()"

# Run backend server
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

**Frontend Setup:**

```bash
cd frontend

# Install dependencies
npm install

# Start dev server
npm run dev

# Build for production
npm run build
```

## 🔐 Authentication

### User Registration

```bash
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "username": "trader1",
    "email": "trader1@example.com",
    "password": "securepassword123"
  }'
```

Response:
```json
{
  "success": true,
  "message": "User registered successfully",
  "data": {
    "user_id": 1,
    "username": "trader1"
  }
}
```

### User Login

```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "username": "trader1",
    "password": "securepassword123"
  }'
```

Response:
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 1800
}
```

### Token Refresh

```bash
curl -X POST http://localhost:8000/api/v1/auth/refresh \
  -H "Authorization: Bearer <refresh_token>"
```

## 📊 API Endpoints

### Authentication Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/auth/register` | Register new user |
| POST | `/api/v1/auth/login` | Login user |
| POST | `/api/v1/auth/refresh` | Refresh access token |
| GET | `/api/v1/users/me` | Get current user profile |

### Backtest Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/backtests` | List all backtests |
| GET | `/api/v1/backtests/{run_id}` | Get backtest details |
| GET | `/api/v1/stats` | Get system statistics |

### WebSocket

| Path | Description |
|------|-------------|
| `/ws/backtest/{run_id}` | Real-time backtest updates |

## 💾 Database Schema

### BacktestRun Table
```sql
CREATE TABLE backtest_runs (
  id SERIAL PRIMARY KEY,
  run_id VARCHAR(50) UNIQUE NOT NULL,
  status VARCHAR(20) DEFAULT 'running',
  created_at TIMESTAMP DEFAULT NOW(),
  started_at TIMESTAMP,
  completed_at TIMESTAMP,
  duration_seconds FLOAT,
  start_date VARCHAR(10),
  end_date VARCHAR(10),
  num_pairs INTEGER,
  total_markets INTEGER,
  total_trades INTEGER DEFAULT 0,
  profitable_trades INTEGER DEFAULT 0,
  win_rate FLOAT,
  total_pnl FLOAT DEFAULT 0.0,
  total_pnl_usd FLOAT DEFAULT 0.0,
  sharpe_ratio FLOAT,
  max_drawdown FLOAT,
  profit_factor FLOAT,
  user_id INTEGER REFERENCES users(id),
  config JSONB
);

CREATE INDEX idx_run_status_created ON backtest_runs(status, created_at);
CREATE INDEX idx_run_user_created ON backtest_runs(user_id, created_at);
```

### BacktestResult Table
```sql
CREATE TABLE backtest_results (
  id SERIAL PRIMARY KEY,
  run_id_fk INTEGER REFERENCES backtest_runs(id),
  market_1 VARCHAR(50),
  market_2 VARCHAR(50),
  total_trades INTEGER DEFAULT 0,
  pnl FLOAT DEFAULT 0.0,
  pnl_usd FLOAT DEFAULT 0.0,
  win_rate FLOAT,
  sharpe_ratio FLOAT,
  max_drawdown FLOAT,
  created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_result_pair ON backtest_results(market_1, market_2);
CREATE INDEX idx_result_run_profit ON backtest_results(run_id_fk, pnl);
```

## 🔌 Environment Variables

### Backend (.env)
```bash
# Database
DB_TYPE=postgresql              # or sqlite
DB_NAME=dydx_backtest
DB_USER=postgres
DB_PASSWORD=password
DB_HOST=localhost
DB_PORT=5432

# JWT
JWT_SECRET_KEY=your-secret-key-change-in-production
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7

# Server
ENVIRONMENT=development        # or production
CORS_ORIGINS=http://localhost:3000,http://localhost:5173
```

### Frontend (.env)
```bash
REACT_APP_API_URL=http://localhost:8000/api/v1
VITE_API_URL=http://localhost:8000/api/v1
```

## 🔗 Connecting Backtest Results to Database

### Store Backtest Results

```python
from backend.services import BacktestRunService, BacktestResultService
from backend.database import SessionLocal

db = SessionLocal()

# Create backtest run
run = BacktestRunService.create_run(
    db=db,
    run_id="backtest_20251017_001",
    start_date="2025-09-17",
    end_date="2025-10-17",
    num_pairs=5,
    total_markets=240,
    user_id=1,
    config={"ZScoreThreshold": 1.2, "statsWindow": 14}
)

# Add results for each pair
for market_1, market_2, metrics in backtest_results:
    BacktestResultService.create_result(
        db=db,
        run_id_fk=run.id,
        market_1=market_1,
        market_2=market_2,
        metrics={
            "total_trades": metrics["trades"],
            "pnl": metrics["pnl"],
            "win_rate": metrics["win_rate"],
            "sharpe_ratio": metrics["sharpe"],
            # ... other metrics
        }
    )

# Update run metrics
BacktestRunService.update_run_metrics(
    db=db,
    run_id_pk=run.id,
    metrics={
        "total_trades": 150,
        "win_rate": 0.65,
        "total_pnl": 1250.0,
        "status": "completed"
    }
)

db.close()
```

## 🖥️ WebSocket Real-Time Updates

### Client Connection

```typescript
// Connect to WebSocket
const ws = new WebSocket(`ws://localhost:8000/ws/backtest/${runId}?token=${accessToken}`);

// Handle messages
ws.onmessage = (event) => {
  const update = JSON.parse(event.data);
  console.log('Status:', update.status);
  console.log('Progress:', update.progress);
  console.log('Message:', update.message);
};

// Handle errors
ws.onerror = (error) => {
  console.error('WebSocket error:', error);
};

// Handle disconnect
ws.onclose = () => {
  console.log('WebSocket disconnected');
};
```

### Server Broadcasting

```python
from backend.main import broadcast_backtest_update, BacktestStatusUpdate

# During backtest execution
await broadcast_backtest_update(
    BacktestStatusUpdate(
        run_id="backtest_001",
        status="running",
        progress=25.5,
        message="Processing pair 10 of 40"
    )
)
```

## 🧪 Testing

### Backend Tests

```bash
pytest backend/tests/ -v --cov=backend
```

### Frontend Tests

```bash
cd frontend
npm test
```

### API Integration Tests

```bash
# Test health check
curl http://localhost:8000/health

# Test API docs
open http://localhost:8000/docs

# Test registration & login flow
python scripts/test_api_flow.py
```

## 🚢 Production Deployment

### Environment Setup

```bash
# Create production .env
cat > .env.production << EOF
DB_TYPE=postgresql
DB_NAME=dydx_backtest_prod
DB_USER=postgres
DB_PASSWORD=$(openssl rand -base64 32)
DB_HOST=your-db-host
DB_PORT=5432

JWT_SECRET_KEY=$(openssl rand -base64 32)
ENVIRONMENT=production
CORS_ORIGINS=https://yourdomain.com

DEBUG=false
EOF
```

### Docker Build & Deploy

```bash
# Build production images
docker-compose -f docker-compose.full-stack.yml build

# Push to registry
docker push your-registry/dydx-backtest-api:latest
docker push your-registry/dydx-backtest-ui:latest

# Deploy to production
docker-compose -f docker-compose.full-stack.yml up -d

# Check logs
docker-compose -f docker-compose.full-stack.yml logs -f
```

### Kubernetes Deployment (Optional)

```bash
# Create namespace
kubectl create namespace dydx-backtest

# Deploy backend
kubectl apply -f k8s/backend-deployment.yaml -n dydx-backtest
kubectl apply -f k8s/backend-service.yaml -n dydx-backtest

# Deploy frontend
kubectl apply -f k8s/frontend-deployment.yaml -n dydx-backtest
kubectl apply -f k8s/frontend-service.yaml -n dydx-backtest
```

## 📈 Performance Optimization

### Database Optimization
- Add indexes on frequently queried columns
- Use connection pooling (SQLAlchemy)
- Archive old backtest results periodically

### API Optimization
- Enable Redis caching for user data
- Use pagination for large result sets
- Implement rate limiting on endpoints

### Frontend Optimization
- Code splitting with React.lazy()
- Image optimization
- Bundle size analysis: `npm run build --analyze`

## 🐛 Troubleshooting

### Database Connection Issues

```bash
# Test PostgreSQL connection
psql -h localhost -U postgres -d dydx_backtest

# Check backend logs
docker-compose -f docker-compose.full-stack.yml logs backend

# Reinitialize database
python -c "from backend.database import init_db, Base, engine; Base.metadata.drop_all(engine); init_db()"
```

### JWT Token Issues

```bash
# Decode JWT token
python -c "import jwt; print(jwt.decode('TOKEN_HERE', options={'verify_signature': False}))"

# Check token expiration
python -c "
from backend.auth import decode_token
token_data = decode_token('TOKEN_HERE')
if token_data:
    print(f'Expires: {token_data.exp}')
    print(f'Type: {token_data.type}')
"
```

### WebSocket Connection Issues

```bash
# Test WebSocket endpoint
wscat -c "ws://localhost:8000/ws/backtest/test_run?token=YOUR_TOKEN"

# Check backend WebSocket connections
docker-compose -f docker-compose.full-stack.yml exec backend \
  python -c "from backend.main import WS_ACTIVE_CONNECTIONS; print(len(WS_ACTIVE_CONNECTIONS))"
```

## 📚 Additional Resources

- [FastAPI Documentation](https://fastapi.tiangolo.com)
- [SQLAlchemy ORM](https://docs.sqlalchemy.org/en/20)
- [React Documentation](https://react.dev)
- [JWT Best Practices](https://tools.ietf.org/html/rfc8725)
- [WebSocket Guide](https://developer.mozilla.org/en-US/docs/Web/API/WebSocket)

## 📞 Support

For issues or questions:
1. Check the troubleshooting section above
2. Review Docker logs: `docker-compose logs -f`
3. Check API docs: http://localhost:8000/docs
4. Review source code comments
