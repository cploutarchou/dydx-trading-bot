# Environment API Routing

Status date: 2026-06-16

## Hostname Rules

Staging browser hostnames route to `https://api.staging.executionlab.io`:

- `staging.executionlab.io`
- any hostname beginning with `staging-`
- any hostname beginning with `staging.`

Production ExecutionLab browser hostnames route to `https://api.executionlab.io`:

- `executionlab.io`
- `www.executionlab.io`
- `app.executionlab.io`
- `admin.executionlab.io`
- other non-staging hostnames default safely to the production API.

The resolver does not use loose `hostname.includes("staging")` matching.

## Configuration Priority

Frontend API resolution is centralized in `frontend/src/api/origin.ts`.

Priority order:

1. Valid runtime config from `window.__EXECUTIONLAB_CONFIG__.apiBaseUrl`.
2. Valid build-time `VITE_API_BASE_URL`, with `VITE_API_URL` retained as compatibility fallback.
3. Runtime hostname detection.
4. `https://api.executionlab.io` as the final safe production fallback.

Configured URLs are validated before use:

- Hosted staging/production API URLs must use HTTPS.
- Approved hosted API hosts are only `api.staging.executionlab.io` and `api.executionlab.io`.
- Localhost API URLs are only accepted for local browser hostnames or Vite dev mode.
- Staging API configuration is rejected on production hostnames.
- Production API configuration is rejected on staging hostnames.

## Local Development

Local Vite development keeps the existing dev-proxy behavior. When `VITE_API_BASE_URL` or `VITE_API_URL` points at `http://localhost:8888` or `http://127.0.0.1:8888`, frontend requests stay relative so the Vite proxy can forward `/api` and `/ws`.

SSR-safe helpers accept an explicit location/runtime context and do not require `window`.

## Kubernetes Runtime Config

Kubernetes manifests are single-file environment manifests:

- `deploy/k8s/dydx-trading-bot-staging.yaml`
- `deploy/k8s/dydx-trading-bot-production.yaml`

Each environment defines a non-secret `dydx-frontend-runtime-config` ConfigMap mounted into the frontend Nginx container at:

```text
/usr/share/nginx/html/executionlab-config.js
```

The browser loads this file before the Vite bundle:

```html
<script src="/executionlab-config.js"></script>
```

The staging file sets:

```js
window.__EXECUTIONLAB_CONFIG__ = {
  apiBaseUrl: "https://api.staging.executionlab.io"
};
```

The production file sets:

```js
window.__EXECUTIONLAB_CONFIG__ = {
  apiBaseUrl: "https://api.executionlab.io"
};
```

No secrets are placed in runtime frontend configuration.

## Ingress And CORS

Staging API ingress:

- Host: `api.staging.executionlab.io`
- TLS host: `api.staging.executionlab.io`
- TLS secret: `api-staging-executionlab-io-tls`

Production API ingress:

- Host: `api.executionlab.io`
- TLS host: `api.executionlab.io`
- TLS secret: `api-executionlab-io-tls`

Staging CORS permits:

- `https://staging.executionlab.io`
- `https://staging-admin.executionlab.io`
- narrowly scoped `https://staging-*.executionlab.io`

Production CORS permits:

- `https://executionlab.io`
- `https://www.executionlab.io`
- `https://app.executionlab.io`
- `https://admin.executionlab.io`

CORS is not widened to `*`.

## Verification Commands

```bash
cd frontend
npm run typecheck
npm run lint
npx vitest run src/api/origin.test.ts
npm run test:contracts
npm run build

cd ../backend
go test ./...
make lint
make build

cd ..
kubectl kustomize deploy/k8s
```

For this repository layout, the deploy directory currently contains complete staging and production YAML files rather than Kustomize overlays.

## Deployment Notes

Do not assume container environment variables are visible to browser JavaScript. The static frontend uses the mounted runtime config file for environment-specific API routing, with hostname detection as a fallback for shared images.
