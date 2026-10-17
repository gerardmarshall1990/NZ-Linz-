"""Bed rules and requirement slots from config. Regulatory values stay blank until sourced; a blank rule is never applied and is reported."""
from functools import lru_cache
import yaml
from .config import ROOT

@lru_cache
def load() -> dict: return yaml.safe_load((ROOT / "config/bed_rules.yaml").read_text())

def reg(name: str):
    return (load()["regulatory"].get(name) or {}).get("value")

def missing_regulatory() -> list[str]:
    return [k for k in load()["regulatory"] if reg(k) is None]

def design() -> dict: return load()["design"]

@lru_cache
def requirements() -> list[dict]: return yaml.safe_load((ROOT / "config/rh_requirements.yaml").read_text())["requirements"]
