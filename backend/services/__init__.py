# Expose commonly used service classes. Use try/except so this package can be imported
# both when running as a module (python -m backend.main) and when running as a
# top-level script (uvicorn main:app).
try:
    from ..db_services import (
        AuditLogService,
        BacktestRunService,
        UserService,
        BacktestResultService,
    )
except Exception:
    from db_services import (
        AuditLogService,
        BacktestRunService,
        UserService,
        BacktestResultService,
    )

