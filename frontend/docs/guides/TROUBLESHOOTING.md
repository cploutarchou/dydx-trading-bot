# Troubleshooting Guide

Common issues and solutions.

## DevContainer

### Container won't build

**Problem:** DevContainer build fails or hangs.

**Solutions:**

```bash
# Option 1: Rebuild from scratch
Ctrl+Shift+P → "Dev Containers: Rebuild Container"

# Option 2: Remove and restart
Ctrl+Shift+P → "Dev Containers: Remove Container"
# Then reopen in container
```

### Port already in use

**Problem:** Port 5173 or other ports already in use.

**Solutions:**

```bash
# Option 1: Stop conflicting services
docker-compose down

# Option 2: Use different port
# Edit: .devcontainer/devcontainer.json
# Change: "forwardPorts": [5174, 3000, 8000, 5432, 6379]
```

### SSH not working

**Problem:** Git operations fail with SSH errors.

**Solutions:**

```bash
# Inside container, check SSH keys
ls -la ~/.ssh

# Test GitHub connection
ssh -T git@github.com

# If keys missing, verify host machine:
# Outside container: ls -la ~/.ssh

# Then rebuild container:
Ctrl+Shift+P → "Dev Containers: Rebuild Container"
```

### Git commits fail

**Problem:** Cannot commit inside container.

**Solutions:**

```bash
# Check git config is mounted
git config --global user.name
git config --global user.email

# If missing, configure outside container and rebuild:
git config --global user.name "Your Name"
git config --global user.email "your.email@example.com"

# Then rebuild container
Ctrl+Shift+P → "Dev Containers: Rebuild Container"
```

### Extensions not installing

**Problem:** VSCode extensions not appearing in DevContainer.

**Solutions:**

```bash
# Option 1: Rebuild container
Ctrl+Shift+P → "Dev Containers: Rebuild Container"

# Option 2: Check .devcontainer/devcontainer.json
# Ensure extensions list is present in customizations section

# Option 3: Manually install extension
# In VS Code: Ctrl+Shift+X → search → Install
```

## npm & Dependencies

### npm install hanging

**Problem:** `npm install` takes forever or hangs.

**Solutions:**

```bash
# Clear cache
npm cache clean --force

# Remove and reinstall
rm -rf node_modules package-lock.json
npm install

# Or use specific npm version
npm install --legacy-peer-deps
```

### Missing dependencies

**Problem:** Module not found errors after installing.

**Solutions:**

```bash
# Clean install
rm -rf node_modules package-lock.json
npm cache clean --force
npm install

# Check package.json is correct
# Verify no syntax errors
```

### Global packages not available

**Problem:** Globally installed packages (`tsx`, `ts-node`, etc.) not found.

**Solutions:**

```bash
# Already installed in container, but if missing:
npm install -g tsx ts-node nodemon

# Check installation
which tsx
```

## Docker & Services

### Docker command not found

**Problem:** `docker` or `docker-compose` command not found inside container.

**Solutions:**

```bash
# Already included in container, restart if needed:
Ctrl+Shift+P → "Dev Containers: Rebuild Container"

# Outside container, ensure Docker is running:
docker ps
```

### Services won't start

**Problem:** `docker-compose up -d` fails.

**Solutions:**

```bash
# Check Docker is running
docker ps

# Check for conflicting containers
docker ps -a

# Remove old containers
docker-compose down -v
docker-compose up -d

# View error logs
docker-compose logs -f
```

### PostgreSQL connection fails

**Problem:** Cannot connect to PostgreSQL at localhost:5432.

**Solutions:**

```bash
# Check service is running
docker-compose ps

# Check logs
docker-compose logs postgres  # or 'db'

# Verify connection parameters
# User: postgres
# Password: postgres
# Database: dydx_trading
# Host: localhost
# Port: 5432

# Or inside container:
docker-compose up -d
# Services should be accessible at localhost
```

### Redis connection fails

**Problem:** Cannot connect to Redis at localhost:6379.

**Solutions:**

```bash
# Check service is running
docker-compose ps

# Test connection
redis-cli ping

# If redis-cli not available, use telnet
telnet localhost 6379
```

## Development Server

### Dev server won't start

**Problem:** `npm run dev` fails or server doesn't start.

**Solutions:**

```bash
# Check port is available
lsof -i :5173  # Linux/Mac
netstat -ano | findstr :5173  # Windows

# Kill process using port
kill -9 <PID>

# Try dev server again
npm run dev

# Or use different port:
npm run dev -- --port 5174
```

### Hot Module Reload (HMR) not working

**Problem:** Changes don't auto-refresh browser.

**Solutions:**

```bash
# Check dev server is running
# Should see: "Local: http://localhost:5173"

# Hard refresh browser
Ctrl+Shift+R (or Cmd+Shift+R on Mac)

# Check vite.config.ts HMR settings
# Should include: hmr: { host: 'localhost', port: 5173 }

# Restart dev server
# Ctrl+C to stop
# npm run dev to restart
```

### Page shows 404

**Problem:** Page shows "cannot GET /path".

**Solutions:**

```bash
# Check React Router configuration
# All routes should default to landing page

# Check dev server is running
# Should see "Local: http://localhost:5173" in terminal

# Verify correct port:
# Dev server runs on 5173, not 3000
```

## Build & Production

### Build fails

**Problem:** `npm run build` throws errors.

**Solutions:**

```bash
# Check for TypeScript errors
npx tsc --noEmit

# Clean build
rm -rf dist .vite
npm run build

# Check for missing dependencies
npm install

# View full error output
npm run build 2>&1 | tail -50
```

### Build output too large

**Problem:** Production build creates large chunks (>500KB).

**Solutions:**

```bash
# Analyze bundle
npm run build  # Shows bundle size analysis

# Enable code splitting:
# Already enabled in vite.config.ts

# Use dynamic imports:
// Instead of:
// import Component from './Component'

// Use:
// const Component = lazy(() => import('./Component'))
```

### Production server won't start

**Problem:** Docker container won't run production build.

**Solutions:**

```bash
# Build production image
docker build -t dydx-frontend .

# Run with verbose output
docker run -it dydx-frontend

# Check Dockerfile for issues
# Should have: CMD ["serve", "-s", "dist", "-l", "3000"]

# Check dist directory exists
npm run build
ls -la dist/
```

## Environment & Configuration

### Environment variables not loading

**Problem:** `process.env` or `import.meta.env` variables are undefined.

**Solutions:**

```bash
# For Vite, use: import.meta.env.VITE_*
// Correct:
const apiUrl = import.meta.env.VITE_API_URL

// Wrong:
const apiUrl = process.env.VITE_API_URL

# Create .env.local
cp .env.local.example .env.local

# Add variables
VITE_API_URL=http://localhost:8000

# Restart dev server for changes to take effect
npm run dev
```

### API calls failing

**Problem:** API requests to backend fail or timeout.

**Solutions:**

```bash
# Check backend is running
curl http://localhost:8000/api/v1/health

# Verify API URL in environment
echo $VITE_API_URL  # Inside container
# Should be: http://localhost:8000

# Check backend logs
docker-compose logs -f backend

# Verify network connectivity
docker-compose exec frontend curl http://backend:8000/api/v1/health

# Check firewall rules
# Ensure ports 8000, 5432, 6379 are accessible
```

## Other Issues

### Slow performance

**Problem:** Dev server slow, builds take too long.

**Solutions:**

```bash
# Restart dev server
npm run dev

# Clear Vite cache
rm -rf .vite
npm run dev

# Check system resources
docker stats

# For slow Docker, increase resources in Docker Desktop settings
# Settings → Resources → Memory/CPU
```

### Permission denied errors

**Problem:** "Permission denied" when running commands.

**Solutions:**

```bash
# Check file permissions
ls -la src/

# For socket errors:
ls -la /var/run/docker.sock

# Rebuild container (usually fixes this)
Ctrl+Shift+P → "Dev Containers: Rebuild Container"
```

### Out of space

**Problem:** "No space left on device" error.

**Solutions:**

```bash
# Clean Docker
docker system prune -a --volumes

# Remove unused images
docker rmi $(docker images -q)

# Clean npm cache
npm cache clean --force

# Remove old containers
docker-compose down -v
```

## Getting More Help

- **DevContainer documentation:** [../devcontainer/README.md](../devcontainer/README.md)
- **Setup guide:** [../SETUP.md](../SETUP.md)
- **Architecture:** [../architecture/](../architecture/)
- **Code patterns:** [../../.github/copilot-instructions.md](../../.github/copilot-instructions.md)

---

**Still stuck?** Check the documentation or create an issue!
