#!/usr/bin/env python3
"""One-time, repeat-safe Sprint 2 integration into EXISTING team files.

Run from repository root: python3 scripts/apply_siddartha_sprint2.py
Does not touch .env or Git, and does not execute any SQL.
"""
from pathlib import Path

root = Path(__file__).resolve().parent.parent
main_file = root / "backend" / "main.py"
schema_file = root / "initialschema.sql"

if not main_file.is_file() or not schema_file.is_file():
    raise SystemExit("ERROR: Run this inside OmniStat's repository (backend/main.py and initialschema.sql required).")

source = main_file.read_text(encoding="utf-8")
if "siddartha_sprint2_router" not in source:
    # Keep API routes ahead of the catch-all app.mount('/', ...), which otherwise
    # intercepts every request to the new endpoints.
    mount_token = 'app.mount("/",'
    if mount_token not in source:
        raise SystemExit("ERROR: Could not locate frontend app.mount; manually include the router BEFORE any '/' mount.")
    code = (
        "# Siddartha Sprint 2 endpoints: registered before the catch-all frontend mount.\n"
        "from backend.siddartha_sprint2 import (\n"
        "    router as siddartha_sprint2_router, FrontendOnlyStaticFiles\n"
        ")\n"
        "app.include_router(siddartha_sprint2_router)\n\n"
    )
    source = source.replace(mount_token, code + mount_token, 1)

# Prevent the existing root StaticFiles mount from publishing .env, .gitignore,
# backend Python source and SQL scripts over HTTP. Preserve the rest of main.py.
mount_line = next((l for l in source.splitlines() if l.startswith('app.mount("/",')), "")
if "StaticFiles(" in mount_line and "FrontendOnlyStaticFiles(" not in mount_line:
    source = source.replace(mount_line, mount_line.replace("StaticFiles(", "FrontendOnlyStaticFiles(", 1), 1)
elif "FrontendOnlyStaticFiles(" not in mount_line:
    raise SystemExit("ERROR: Unsupported frontend mount; check backend/main.py before running app.")

# If the route was included previously without this import, make sure safe
# frontend class is available. This is also useful when applying twice.
if "FrontendOnlyStaticFiles" not in source.split('app.mount("/",')[0]:
    source = source.replace('app.mount("/",',
        'from backend.siddartha_sprint2 import FrontendOnlyStaticFiles\napp.mount("/",', 1)

main_file.write_text(source, encoding="utf-8")

warning = (
    "-- WARNING: DESTRUCTIVE DEVELOPMENT RESET SCRIPT!\n"
    "-- Running this file DROPS tables and can erase accounts, sales, and business data.\n"
    "-- Never run on a populated/production database; back up data first.\n"
    "-- For Sprint 2 updates run migrations/003_siddartha_sprint2.sql instead.\n\n"
)
schema = schema_file.read_text(encoding="utf-8")
if "DESTRUCTIVE DEVELOPMENT RESET SCRIPT!" not in schema:
    schema_file.write_text(warning + schema, encoding="utf-8")

print("Sprint 2 routes installed; original authentication code preserved.")
print("Frontend mount restricted to public frontend file types.")
print("Schema reset warning added to initialschema.sql.")
print("NEXT: Run the ADDITIVE SQL migration manually on the intended test database.")
