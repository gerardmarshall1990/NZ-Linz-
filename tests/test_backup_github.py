"""Runs the shell test of the encrypted private-repo backup (local bare repo, no network)."""
import subprocess
from pathlib import Path
import pytest
ROOT = Path(__file__).resolve().parent.parent
def test_backup_to_private_repo_refuses_unsafe_and_pushes_only_encrypted():
    r = subprocess.run(["bash", str(ROOT / "tests/test_backup_github.sh")], capture_output=True, text=True, cwd=ROOT, timeout=300)
    assert r.returncode == 0, r.stdout + r.stderr
    for f in (ROOT / "backups").glob("userdata_*.tar.gpg"): f.unlink()      # test artefacts only
