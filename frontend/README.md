# dYdX Trading Bot Frontend

React + TypeScript frontend for the dYdX trading dashboard and backtest workflows.

## Quick start

```bash
npm install
make stack-env
make infra-up
npm run dev
```

Visit <http://localhost:5173> for local development.

## Prerequisites

- **Development:** Node 20+, npm, and access to the repo-root `.env`
- **Integration services:** Docker + `make`

## Common commands

```bash
npm run dev
npm run build
npm run lint
npm run preview
make infra-up
make stack-up-dev
```

## Documentation

Use the docs in this order:

1. **[Documentation Home](docs/README.md)** - main frontend documentation entry point
2. **[Setup Guide](docs/SETUP.md)** - local setup, build, preview, and integration commands
3. **[Troubleshooting](docs/guides/TROUBLESHOOTING.md)** - common issues and fixes
4. **[Architecture](docs/architecture/README.md)** - data flow, patterns, and API structure
5. **[Code Patterns](.github/copilot-instructions.md)** - project conventions and implementation guidance

Detailed setup, preview, and Docker usage live in [docs/SETUP.md](docs/SETUP.md).

## Project structure

```text
src/
├── components/       # Reusable React components
├── pages/           # Route-level components
├── store/           # Zustand state management
├── api.ts           # API client with interceptors
└── hooks/           # Custom React hooks

docs/               # All documentation
├── architecture/   # System design
└── guides/         # Detailed guides
```

## Tech stack

- **React 19** + **TypeScript** + **Vite**
- **Zustand** (state management)
- **TailwindCSS v4** (styling)
- **Recharts** (data visualization)
- **Axios** (HTTP client)
- **React Router** (navigation)

## Architecture

For detailed architecture information, see [docs/architecture/README.md](docs/architecture/README.md).

## Code patterns

See [.github/copilot-instructions.md](.github/copilot-instructions.md) for project-specific conventions and implementation patterns.

## Contributing

1. Create a branch from `master`
2. Make your changes
3. Run: `npm run lint -- --fix`
4. Commit with descriptive messages
5. Push and create a pull request

## Help

- **Setup issues?** → [docs/SETUP.md](docs/SETUP.md)
- **Troubleshooting?** → [docs/guides/TROUBLESHOOTING.md](docs/guides/TROUBLESHOOTING.md)
- **Architecture questions?** → [docs/architecture/](docs/architecture/)
- **Code patterns?** → [.github/copilot-instructions.md](.github/copilot-instructions.md)

## License

See LICENSE file in root directory

---

Start with [docs/SETUP.md](docs/SETUP.md).
