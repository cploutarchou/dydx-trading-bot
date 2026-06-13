# Scripts Usage Audit

- Generated: 2026-06-12
- Scope: tracked `scripts/*` files mapped to operational references in Makefiles, workflows, and deploy hooks

## Operational files scanned

- `.github/workflows/container-images.yml`
- `Makefile`
- `backend/Makefile`
- `bot/Makefile`
- `deploy/nomad/README.md`
- `deploy/nomad/dydx-trading-bot.nomad.hcl`
- `deploy/nomad/production.nomad.vars.hcl.example`
- `frontend/Makefile`

## Scripts still present and operational references

| Script                                  | Operational references                                 | Status                              | Manual purpose note                                                                                                                       |
| --------------------------------------- | ------------------------------------------------------ | ----------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------- |
| `scripts/analyze_backtest_results.py`   | `Makefile`                                             | referenced                          | —                                                                                                                                         |
| `scripts/build_all_service_images.sh`   | `Makefile`                                             | referenced                          | —                                                                                                                                         |
| `scripts/celery-flower.sh`              | `Makefile`                                             | referenced                          | —                                                                                                                                         |
| `scripts/check_no_legacy_database.py`   | `.github/workflows/container-images.yml`, `Makefile`   | referenced                          | —                                                                                                                                         |
| `scripts/edit_config.py`                | `Makefile`                                             | referenced                          | —                                                                                                                                         |
| `scripts/init_database.py`              | `Makefile`                                             | referenced                          | —                                                                                                                                         |
| `scripts/install_security_tools.sh`     | `Makefile`                                             | referenced                          | —                                                                                                                                         |
| `scripts/manage_bot.sh`                 | `Makefile`                                             | referenced                          | —                                                                                                                                         |
| `scripts/migrate_yaml_configs_to_db.py` | —                                                      | no operational hook reference found | One-time operator migration tool for deprecated `bot_states/config_*.yaml` into DB (`bot_instances.config`); workers no longer read YAML. |
| `scripts/render_run_config.py`          | `Makefile`                                             | referenced                          | —                                                                                                                                         |
| `scripts/run_backtest.py`               | `Makefile`                                             | referenced                          | —                                                                                                                                         |
| `scripts/secure_config.py`              | `Makefile`                                             | referenced                          | —                                                                                                                                         |
| `scripts/test_loki.py`                  | `Makefile`                                             | referenced                          | —                                                                                                                                         |
| `scripts/validate_docs_governance.py`   | `Makefile`                                             | referenced                          | —                                                                                                                                         |
| `scripts/validate_stack_env.py`         | `Makefile`                                             | referenced                          | —                                                                                                                                         |

## Notes

- "Operational references" means literal mentions in Makefiles, `.github/workflows/*`, `deploy/*`, or root deploy/compose manifests.
- A script may still be useful for ad-hoc/manual operations even when no hook reference exists.
