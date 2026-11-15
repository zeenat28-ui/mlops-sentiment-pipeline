import subprocess, sys, pathlib, os

# Get project root - works in both notebook and script environments
if '__file__' in globals():
    # Running as script
    root = pathlib.Path(__file__).resolve().parent.parent
else:
    # Running in notebook environment (Databricks jobs)
    # Bundle deploys files to .bundle/<bundle_name>/<target>/files/
    root = pathlib.Path(os.getcwd())
    # If we're in the src directory, go up one level
    if root.name == 'src':
        root = root.parent

r = subprocess.run([sys.executable, "-m", "pytest", "-q", str(root / "tests")], cwd=root)
sys.exit(r.returncode)
