import subprocess, sys, pathlib
root = pathlib.Path(__file__).resolve().parent.parent
r = subprocess.run([sys.executable, "-m", "pytest", "-q", str(root / "tests")], cwd=root)
sys.exit(r.returncode)
