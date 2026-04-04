## Summary
- Describe what changed and why.

## Integration Impact
- Endpoint(s) changed:
- Request payload change:
- Response payload change:
- Auth/middleware impact:
- DB/schema/sync impact:

## Cross-Service Task Governance Checklist
- [ ] Updated `backend/tasks.md` status/checklist and change log.
- [ ] Updated `../bot/tasks.md` when bot integration behavior changed.
- [ ] Updated `../frontend/tasks.md` when frontend integration behavior changed.
- [ ] Ran `make tasks-governance` and confirmed summaries/validation pass.
- [ ] If API contract changed, added/updated contract-lock tests in `internal/routes/contract_lock_integration_test.go`.

## Validation
- Commands run:
```bash
make tasks-governance
make test
```

