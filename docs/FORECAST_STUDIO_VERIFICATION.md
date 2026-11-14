# ForecastStudio and DemandPulse — verification record

## Measurements from the authoring environment (2026-11-13)

- **37 passed** in an isolated mocked test harness: 20 original forecast tests + 12 DemandPulse logic tests + 5 DemandPulse API tests.
- Python compilation checks passed on all new source and test modules.
- `node --check` passed on ForecastStudio, preview and DemandPulse JavaScript modules.
- Installer dry-run, initial install, repeat install and upgrade-from-pristine-v1 checks are performed in a synthetic Git checkout; no user's live repository was changed.
- The baseline data used by unit tests is synthetic and is **not proof of forecast accuracy at a real restaurant**.

## Your Mac: mandatory verification still pending

```bash
./.venv/bin/python -m pytest -q tests/test_forecast_engine.py tests/test_forecast_api.py tests/test_forecast_monitor.py tests/test_forecast_monitor_api.py
./.venv/bin/python -m pytest -q
node --check forecast-studio.js
node --check forecast-preview.js
node --check forecast-accuracy.js
./.venv/bin/python - <<'PY'
from backend.main import app
paths=app.openapi()["paths"]
for path in ("/api/forecast/overview", "/api/forecast/reorder-scenario", "/api/forecast/accuracy"):
    assert path in paths, path
    print("Registered:",path)
PY
./.venv/bin/python -m scripts.forecast_demo
```

- Sign in as **business owner**; open `forecast-studio.html`, 7/30/90/365 horizon controls, category/product selection, DemandPulse 7/30-day replay, stock scenario.
- Sign in as a regular employee or without a token; owner-only endpoints must reject unauthorized access.
- Verify the API against your **actual development PostgreSQL schema** and representative signed refunds, date boundary and sparse-upload cases. This has not been done in the author's offline environment.
- For measured query plans and execution times, run `scripts/forecast_pg_plan.py` with a known development business UUID. Query plan and timings are pending, not estimated.

**Performance statement:** No index was added and no SQL workload was optimized in this release; do not claim a before/after speedup.

**Security statement:** The mocked tests show tenant IDs are derived from authorization dependencies rather than query params. A live authentication and PostgreSQL isolation test is still required before claiming production security readiness.
