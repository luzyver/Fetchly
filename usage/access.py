from dataclasses import dataclass
from enum import StrEnum

from usage.identity import VisitorIdentity


class AccessDecision(StrEnum):
    ALLOW = "allow"
    BLOCK = "block"
    DEFAULT = "default"


@dataclass(frozen=True)
class Rule:
    kind: str
    subject_type: str
    subject_value: str


def decide_access(
    rules: list[Rule], identity: VisitorIdentity, normalized_ip: str
) -> AccessDecision:
    subjects = {
        "fingerprint": identity.fingerprint_id,
        "ip_hash": identity.ip_id,
        "owner": identity.owner_id,
        "ip": normalized_ip,
    }
    matching_kinds = {
        rule.kind for rule in rules if subjects.get(rule.subject_type) == rule.subject_value
    }
    if "whitelist" in matching_kinds:
        return AccessDecision.ALLOW
    if "blacklist" in matching_kinds:
        return AccessDecision.BLOCK
    return AccessDecision.DEFAULT
