# DevContainer Quick Start (30 seconds!)

## 3 Steps to Get Started

### 1. Open in VS Code

```bash
code frontend/
```

### 2. Reopen in Container

- VS Code shows "Reopen in Container" popup
- Click it, or: `Ctrl+Shift+P` → "Dev Containers: Reopen in Container"

### 3. Start Development

```bash
npm run dev
```

Visit: **<http://localhost:5173>**

Done! ✅

## What Just Happened?

- ✅ DevContainer built (~2-5 min first time, <10s after)
- ✅ Extensions auto-installed
- ✅ Dependencies auto-installed
- ✅ SSH keys & Git config mounted automatically
- ✅ Dev server running with HMR (auto-refresh)

## Available Commands

```bash
npm run dev         # Dev server
npm run build       # Production build
npm run lint        # Code quality
npm run lint -- --fix  # Auto-fix issues
```

## SSH & Git Setup

✅ **Automatic!**

- Your SSH keys (`~/.ssh`) mounted (read-only)
- Your Git config (`~/.gitconfig`) mounted (read-only)
- Use git normally:

  ```bash
  git add .
  git commit -m "feat: description"
  git push origin main
  ```

## Docker Services (Optional)

Start backend services:

```bash
docker-compose up -d
# PostgreSQL + Redis + Backend API running
```

Stop services:

```bash
docker-compose down
```

## Need Help?

- **Full DevContainer guide:** [README.md](README.md)
- **Setup troubleshooting:** [../guides/TROUBLESHOOTING.md](../guides/TROUBLESHOOTING.md)
- **Architecture info:** [../architecture/](../architecture/)

## Extensions Included

- ESLint + Prettier (formatting)
- TypeScript support
- Tailwind CSS IntelliSense
- React snippets
- Docker integration
- GitLens
- GitHub Copilot
- +8 more tools

---

**That's it! Happy coding! 🚀**
