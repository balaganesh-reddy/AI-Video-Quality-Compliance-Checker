import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass
class ComplianceRules:
    minimum_width: int = 1280
    minimum_height: int = 720
    minimum_fps: float = 24.0
    minimum_duration_seconds: float = 1.0
    maximum_duration_seconds: float = 7200.0


def load_rules(path="compliance_rules.json"):
    config_path = Path(path)
    if not config_path.exists():
        return ComplianceRules()
    with config_path.open("r", encoding="utf-8") as handle:
        values = json.load(handle)
    defaults = ComplianceRules()
    return ComplianceRules(**{**asdict(defaults), **values})


def save_rules(rules, path="compliance_rules.json"):
    with Path(path).open("w", encoding="utf-8") as handle:
        json.dump(asdict(rules), handle, indent=2)
