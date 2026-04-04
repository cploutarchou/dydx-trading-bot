# Troubleshooting Guide

Common local development issues and fixes.

## Git & local environment

### SSH not working

**Problem:** Git operations fail with SSH errors.

**Solutions:**

```bash
ls -la ~/.ssh
ssh -T git@github.com
```

### Git commits fail

**Problem:** Git identity is not configured.

**Solutions:**

```bash
git config --global user.name "Your Name"
git config --global user.email "your.email@example.com"
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

### Global npm packages fail during image build

**Problem:** Docker image build fails with `exit code: 243` during npm global install.

**Error Message:** `npm install -g ... did not complete successfully: exit code: 243`

**Solutions:**

```bash
# Option 1: Rebuild without cache
docker build --no-cache -t dydx-frontend .

# Option 2: Check network/registry
npm config set registry https://registry.npmjs.org/
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
# Install the missing global package if your workflow requires it:
npm install -g tsx ts-node nodemon

# Check installation
which tsx
```

## Docker & Services

### Docker command not found

**Problem:** `docker` is not available locally.

**Solutions:**

```bash
docker ps
```

### Services won't start

**Problem:** Integration services fail to start.

**Solutions:**

```bash
# Check Docker is running
docker ps

# Start repo-root infra stack
make stack-env
make infra-up

# View error logs
make infra-logs
```

### PostgreSQL connection fails

**Problem:** Cannot connect to PostgreSQL at localhost:5432.

**Solutions:**

```bash
# Check service is running
make infra-ps

# Check logs
make infra-logs

# Verify connection parameters
# User: postgres
# Password: postgres
# Database: dydx_trading
# Host: localhost
# Port: 5432

# Start shared infra if needed
make infra-up
```

### Redis connection fails

**Problem:** Cannot connect to Redis at localhost:6379.

**Solutions:**

```bash
# Check service is running
make infra-ps

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
lsof -i :5173  # macOS/Linux

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

# Create repo-root .env
cp ../.env.example ../.env

# Add variables
VITE_API_URL=http://localhost:8888

# Restart dev server for changes to take effect
npm run dev
```

### API calls failing

**Problem:** API requests to the Go backend fail or timeout.

**Solutions:**

```bash
# Check backend is running (UI flow)
curl http://localhost:8888/api/v1/health

# Verify API URL in environment
echo $VITE_API_URL
# Should be: http://localhost:8888

# Check backend logs
make stack-logs

# Check firewall rules
# Ensure ports 8888 (UI backend), 5432, 6379 are accessible
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

# If Docker-backed services are slow, increase Docker resources if needed
```

### Permission denied errors

**Problem:** "Permission denied" when running commands.

**Solutions:**

```bash
# Check file permissions
ls -la src/

# For socket errors:
ls -la /var/run/docker.sock

# Check workspace ownership and retry
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

# Remove old containers and volumes
make stack-down
```

## Getting More Help

- **Setup guide:** [../SETUP.md](../SETUP.md)
- **Architecture:** [../architecture/](../architecture/)
- **Code patterns:** [../../.github/copilot-instructions.md](../../.github/copilot-instructions.md)

---

**Still stuck?** Check the documentation or create an issue!
