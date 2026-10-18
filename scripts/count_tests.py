"""Print the real test total (CI uses this; never swallow it with -qq)."""
import subprocess
import sys

out = subprocess.run(
    [sys.executable, "-m", "pytest", "tests/", "-q"],
    capture_output=True, text=True, cwd=".",
)
print(out.stdout.strip().splitlines()[-1])
