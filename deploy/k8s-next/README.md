# k8s next target skeleton

This directory contains the production-shaped k3s target layout for the open-source migration path.

It intentionally keeps secrets out of Git:

- app and data workloads only reference Kubernetes Secrets by name/key
- no plaintext credentials are embedded in the manifests
- schema migrations run as explicit Jobs, not on application startup

For local bootstrap, copy `secrets.local-secret.yaml.example` to
`secrets.local-secret.yaml`, replace the placeholders, and keep the copied file
out of Git.

The resources here are a skeleton. Replace the placeholder image tags, hosts, and secret names with your real deployment values before applying to a cluster.
