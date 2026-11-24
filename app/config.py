import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass
class ComplianceRules:
    # Longest acceptable continuous gap without a detected hand.
    maximum_hand_absence_seconds: float = 60.0
    # A wrist is considered visible when the pose model confidence meets this value.
    minimum_wrist_visibility_confidence: float = 0.5
    # Minimum fraction of analyzed frames whose average luminance is above the threshold.
    minimum_well_lit_frame_ratio: float = 0.75
    minimum_average_brightness: float = 55.0
    phone_detection_confidence: float = 0.35
    sample_interval_seconds: float = 1.0


def load_rules(path="compliance_rules.json"):
    config_path = Path(path)
    if not config_path.exists():
        return ComplianceRules()
    with config_path.open("r", encoding="utf-8") as handle:
        values = json.load(handle)
    defaults = asdict(ComplianceRules())
    # Ignore obsolete settings so older configuration files can be upgraded safely.
    valid_keys = defaults.keys()
    return ComplianceRules(**{**defaults, **{key: value for key, value in values.items() if key in valid_keys}})


def save_rules(rules, path="compliance_rules.json"):
    with Path(path).open("w", encoding="utf-8") as handle:
        json.dump(asdict(rules), handle, indent=2)
