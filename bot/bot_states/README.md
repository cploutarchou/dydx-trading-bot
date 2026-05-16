# bot_states

This directory is for generated runtime logs and per-instance state artifacts.

Deprecated `config_<instance_id>.yaml` files are no longer read by workers in any
environment. Migrate them into `bot_instances.config` with:

```bash
bot/.venv/bin/python scripts/migrate_yaml_configs_to_db.py
```

After validating the DB payloads, remove the deprecated YAML files locally.
