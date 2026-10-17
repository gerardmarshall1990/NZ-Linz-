"""Settings and the Property Record field catalogue. Secrets come only from .env (never logged)."""
import os
from functools import lru_cache
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[2]

def load_env() -> None:
    f = ROOT / ".env"
    if f.exists():
        for line in f.read_text().splitlines():
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1); os.environ.setdefault(k, v)

load_env()

def dsn() -> str:
    return (f"host={os.environ.get('PGHOST', 'localhost')} dbname={os.environ['POSTGRES_DB']} "
            f"user=app_rw password={os.environ['APP_RW_PASSWORD']}")

def upload_dir() -> Path:
    d = Path(os.environ.get("UPLOAD_DIR", "uploads"))
    d = d if d.is_absolute() else ROOT / d
    d.mkdir(parents=True, exist_ok=True)
    return d

@lru_cache
def field_catalogue() -> dict:
    return yaml.safe_load((ROOT / "config/rh_property_fields.yaml").read_text())

MAX_UPLOAD_BYTES = 60 * 1024 * 1024
