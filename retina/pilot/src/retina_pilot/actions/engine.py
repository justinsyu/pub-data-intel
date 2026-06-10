"""Deterministic rule engine: dimension scores and facts in, cited role actions out."""
import operator
from pathlib import Path

import yaml

OPS = {"<=": operator.le, ">=": operator.ge, "<": operator.lt, ">": operator.gt, "==": operator.eq}
RULES_PATH = Path(__file__).parent / "rules.yaml"


def load_rules(path: Path = RULES_PATH) -> list[dict]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _native(value):
    """Cast numpy scalars (from parquet rows) to native Python so evidence is JSON-serializable."""
    return value.item() if hasattr(value, "item") else value


def generate_actions(geo: dict, rules: list[dict]) -> list[dict]:
    out = []
    for rule in rules:
        evidence = []
        for cond in rule["when"]:
            value = geo.get(cond["metric"])
            if value is None or not OPS[cond["op"]](value, cond["value"]):
                evidence = None
                break
            evidence.append({"metric": cond["metric"], "value": _native(value)})
        if evidence is not None:
            out.append({"rule_id": rule["id"], "role": rule["role"],
                        "action": rule["action"], "evidence": evidence})
    return out
