import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass
class ComplianceRules:
    # Fail when a sampled frame contains a face that the age model assigns to a
    # child/minor-like age bucket with at least this confidence.
    maximum_phone_use_seconds: float = 120.0
    minimum_wrist_visible_frame_ratio: float = 0.90
    minimum_wrist_visibility_confidence: float = 0.60
    minimum_well_lit_frame_ratio: float = 0.75
    minimum_average_brightness: float = 55.0
    phone_detection_confidence: float = 0.35
    nsfw_detection_confidence: float = 0.65
    minor_detection_confidence: float = 0.60
    maximum_hand_absence_seconds: float = 60.0
    sample_interval_seconds: float = 1.0


def load_rules(path="compliance_rules.json"):
    config_path = Path(path)
    if not config_path.exists():
        return ComplianceRules()
    with config_path.open("r", encoding="utf-8") as handle:
        values = json.load(handle)
    defaults = asdict(ComplianceRules())
    valid = {key: value for key, value in values.items() if key in defaults}
    return ComplianceRules(**{**defaults, **valid})


def save_rules(rules, path="compliance_rules.json"):
    with Path(path).open("w", encoding="utf-8") as handle:
        json.dump(asdict(rules), handle, indent=2)
