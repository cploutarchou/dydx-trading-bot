# k8s next target skeleton

This directory contains the production-shaped k3s target layout for the open-source migration path.

It intentionally keeps secrets out of Git:

- app and data workloads only reference Kubernetes Secrets by name/key
- no plaintext credentials are embedded in the manifests
- schema migrations run as explicit Jobs, not on application startup

For local bootstrap, copy `secrets.local-secret.yaml.example` to
`secrets.local-secret.yaml`, replace the placeholders, and keep the copied file
out of Git.

Overlay entry points:

- `overlays/staging` for smaller replica counts and staging hostnames
- `overlays/production` for production hostnames and the full base bundle

The resources here are a skeleton. Replace the placeholder image tags, hosts, and secret names with your real deployment values before applying to a cluster.

## Infrastructure contract

`platform-config.yaml` now carries the shared non-secret service-discovery values for:

- PostgreSQL / PgBouncer via `DATABASE_URL` secrets plus `POSTGRES_*`, `DB_*`, `BOT_DB_*`
- Valkey via `REDIS_URL`, `VALKEY_URL`, `REDIS_*`, `VALKEY_*`
- NATS via `NATS_URL` and `NATS_MONITORING_URL` for the optional command bus contract
- ClickHouse via `CLICKHOUSE_URL` and `CLICKHOUSE_*` for the optional analytical writer path
- MinIO via `MINIO_ENDPOINT`, `MINIO_CONSOLE_URL`, `MINIO_BUCKET`, `S3_ENDPOINT`, `S3_REGION`, `S3_FORCE_PATH_STYLE` for the default backtest artifact path

Checked-in k3s defaults keep PostgreSQL as the active transactional persistence path, enable the MinIO-backed
backtest artifact path, and still leave ClickHouse disabled:

- `BACKTEST_ARTIFACT_STORAGE_ENABLED=true`
- `BACKTEST_CLICKHOUSE_WRITES_ENABLED=false`
- `BACKTEST_MINIO_ARTIFACTS_ENABLED=true`

`applications.yaml` injects only non-secret infrastructure config from the ConfigMap and keeps credentials in Secrets.
