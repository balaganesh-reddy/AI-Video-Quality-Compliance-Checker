import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass
class ComplianceRules:
    # Fail when both task-relevant wrists are not clearly visible for this fraction of samples.
    minimum_wrist_visible_frame_ratio: float = 0.90
    minimum_wrist_visibility_confidence: float = 0.60
    # Fail when likely phone use persists beyond this duration (default 2 minutes).
    maximum_phone_use_seconds: float = 120.0
    phone_detection_confidence: float = 0.35
    # Lighting requirements.
    minimum_well_lit_frame_ratio: float = 0.75
    minimum_average_brightness: float = 55.0
    # Retain general hand absence as an additional review signal.
    maximum_hand_absence_seconds: float = 60.0
    sample_interval_seconds: float = 1.0


def load_rules(path="compliance_rules.json"):
    config_path = Path(path)
    if not config_path.exists():
        return ComplianceRules()
    with config_path.open("r", encoding="utf-8") as handle:
        values = json.load(handle)
    defaults = asdict(ComplianceRules())
    valid_values = {key: value for key, value in values.items() if key in defaults}
    return ComplianceRules(**{**defaults, **valid_values})


def save_rules(rules, path="compliance_rules.json"):
    with Path(path).open("w", encoding="utf-8") as handle:
        json.dump(asdict(rules), handle, indent=2)
