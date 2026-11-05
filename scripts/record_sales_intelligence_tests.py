"""Run all OmniStat Python tests and write honest Git-tracked test evidence.

Run from repo root: python scripts/record_sales_intelligence_tests.py
Returns a nonzero exit status if pytest fails.
"""
from datetime import datetime
from pathlib import Path
import platform
import re
import subprocess
import sys


def git(*args):
    return subprocess.check_output(["git", *args], text=True).strip()


def main():
    docs = Path("docs")
    docs.mkdir(exist_ok=True)
    command = [sys.executable, "-m", "pytest", "-v", "--tb=short"]
    run = subprocess.run(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    output = run.stdout
    (docs / "SALES_INTELLIGENCE_PYTEST_OUTPUT.txt").write_text(output)
    print(output)
    summary = next(
        (line.strip() for line in reversed(output.splitlines())
         if re.search(r"\b\d+\s+(?:passed|failed|error|errors|skipped)\b", line)),
        "No pytest summary found",
    )
    files = sorted(set(re.findall(r"(?m)^(tests/[^:\s]+\.py)::", output)))
    report = f"""# OmniStat Sales Intelligence — Test Execution Evidence

- **Execution date:** {datetime.now().astimezone():%Y-%m-%d %H:%M:%S %Z}
- **Branch:** `{git('branch', '--show-current')}`
- **Commit before test execution:** `{git('rev-parse', '--short', 'HEAD')}`
- **Python:** `{platform.python_version()}`
- **Result:** {summary}
- **Process exit status:** {run.returncode} (0 means all pytest checks passed)

## Test modules executed

""" + "\n".join(f"- `{name}`" for name in files) + """

## Important scope note

The automated tests exercise Python APIs, database query behavior via mocks,
CSV parsing, product mix calculations, refund adjustments, and reporting
logic. They do **not** prove that a live browser uploaded files and updated
PostgreSQL. Those steps must be completed and recorded separately.

## Live integration acceptance checklist (complete after manual testing)

- [ ] Upload a CSV with current-period dates against local PostgreSQL
- [ ] Dashboard net sales and product mix match the uploaded CSV
- [ ] Switch between 7 / 30 / 90 day reporting windows
- [ ] Change trend granularity between daily and monthly
- [ ] Compare category growth and day-of-week averages
- [ ] Confirm account, team and invitation workflows still work
- [ ] Verify a second business cannot access this business's sales
- [ ] Check responsive layout on mobile

## Evidence file

`docs/SALES_INTELLIGENCE_PYTEST_OUTPUT.txt`
"""
    (docs / "SALES_INTELLIGENCE_TEST_REPORT.md").write_text(report)
    print("Test evidence saved under docs/SALES_INTELLIGENCE_*.txt and .md")
    return run.returncode


if __name__ == "__main__":
    sys.exit(main())
