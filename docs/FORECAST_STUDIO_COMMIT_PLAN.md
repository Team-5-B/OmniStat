# ForecastStudio + DemandPulse: release and professional Git commits

1. **Check branch and existing work.** `git status --short` and `git branch --show-current`. If `feat/daily-revenue-reconciliation` is still uncommitted, finish it before moving to the ForecastStudio feature. Work on a new feature branch of the correct base; don't forcibly switch branches with unsaved changes.
2. Extract ZIP outside repo, run `install_forecaststudio.py --dry-run`, then the installer. The installer handles fresh installations and pristine original-v1 upgrades without replacing local custom edits.
3. Run all focused tests, the *entire* OmniStat suite, JavaScript syntax checks, route inspection, signed-in owner/employee browser checks, and optionally local PostgreSQL query plans. Do not commit while any required verification fails.

## Meaningful commit groups (run from repository root)

```bash
# 1. Owner-scoped forecast engine, planning and historical replay APIs.
git add backend/forecast_engine.py backend/demand_forecasting.py backend/forecast_monitor.py backend/main.py
git diff --cached --check
git commit -m "feat(forecasting): add tenant-scoped demand planning and historical replay APIs"

# 2. Forecast and accuracy dashboards, owner overview preview.
git add dashboard.html forecast-studio.html forecast-studio.css forecast-studio.js forecast-accuracy.css forecast-accuracy.js forecast-preview.css forecast-preview.js
git diff --cached --check
git commit -m "feat(dashboard): add predictive demand workspace and accuracy monitoring"

# 3. Quality gates, synthetic demo, performance tooling and research reference.
git add tests/test_forecast_engine.py tests/test_forecast_api.py tests/test_forecast_monitor.py tests/test_forecast_monitor_api.py scripts/forecast_demo.py scripts/forecast_pg_plan.py docs/FORECAST_STUDIO_TECHNICAL.md docs/DEMANDPULSE_TECHNICAL.md docs/OMNISTAT_IMPLEMENTATION_ROADMAP.md docs/FORECAST_STUDIO_COMMIT_PLAN.md docs/FORECAST_STUDIO_VERIFICATION.md docs/research/
git diff --cached --check
git commit -m "test(forecasting): verify model replay and document analytics roadmap"

# Push only when approved / ready:
git status --short
git push -u origin "$(git branch --show-current)"
```

Only commit the named changes. `install_forecaststudio.py` is a release artifact outside the project; it need not be committed to the application. Avoid committing `.env`, fixture customer records, Python environments, databases, or secrets. Open a GitHub pull request into `main`; use a normal merge strategy in coordination with the team.

**PR title:** `feat(forecasting): introduce ForecastStudio and DemandPulse insights`

**PR review questions:** Do unit forecasts describe the expected *sold-product* units rather than inventory needs? Does historical replay clearly distinguish reconstructed baselines from previously saved forecasts? Are data gaps identified before stock decisions? Are all routes owner scoped?
