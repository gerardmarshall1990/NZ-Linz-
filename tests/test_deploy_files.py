"""Deployment files: shell syntax, the backup refuses to run unencrypted, service files point at scripts that exist, requirements are pinned."""
import os, re, subprocess
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent

def test_shell_scripts_have_valid_syntax():
    for f in ["deploy/server_setup.sh", "scripts/nightly_backup.sh", "scripts/restore_userdata.sh", "scripts/restore_drill.sh", "scripts/run_tests_safely.sh", ".githooks/pre-push"]:
        r = subprocess.run(["bash", "-n", str(ROOT / f)], capture_output=True, text=True); assert r.returncode == 0, (f, r.stderr)

def test_setup_script_checks_its_inputs_and_changes_nothing_in_check_mode():
    env = {k: v for k, v in os.environ.items() if k not in ("APP_PASSWORD", "TS_AUTHKEY", "LINZ_API_KEY", "BACKUP_PASSPHRASE")}
    r = subprocess.run(["bash", str(ROOT / "deploy/server_setup.sh")], capture_output=True, text=True, env={**env, "CHECK": "1"}); assert r.returncode == 2 and "MISSING: TS_AUTHKEY" in r.stdout
    r = subprocess.run(["bash", str(ROOT / "deploy/server_setup.sh")], capture_output=True, text=True, env={**env, "CHECK": "1", "APP_PASSWORD": "x" * 12, "TS_AUTHKEY": "k", "LINZ_API_KEY": "k", "BACKUP_PASSPHRASE": "short"})
    assert "at least 16" in r.stdout

def test_nightly_backup_refuses_without_a_passphrase(tmp_path):
    env = {k: v for k, v in os.environ.items() if k != "BACKUP_PASSPHRASE"}
    r = subprocess.run(["bash", str(ROOT / "scripts/nightly_backup.sh")], capture_output=True, text=True, env=env); assert r.returncode == 2 and "REFUSED" in r.stdout

def test_service_files_reference_existing_scripts_and_the_app_is_local_only():
    txt = "".join((ROOT / "deploy" / f).read_text() for f in ["nz-linz-app.service", "nz-linz-bootstrap.service", "nz-linz-backup.service"])
    for s in set(re.findall(r"scripts/[a-z_]+\.sh", txt)): assert (ROOT / s).exists(), s
    assert "--host 127.0.0.1" in txt and "0.0.0.0" not in txt
    assert "127.0.0.1:5432:5432" in (ROOT / "deploy/server_setup.sh").read_text()
    assert "OnCalendar" in (ROOT / "deploy/nz-linz-backup.timer").read_text()

def test_requirements_are_pinned_and_cover_the_imports():
    req = (ROOT / "requirements.txt").read_text().lower()
    for pkg in ["fastapi", "uvicorn", "psycopg", "shapely", "pymupdf", "reportlab", "ezdxf", "pyyaml", "pillow", "python-multipart"]: assert re.search(rf"^{pkg}==", req, re.M), pkg
