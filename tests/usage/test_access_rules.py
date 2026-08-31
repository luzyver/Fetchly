from usage.access import AccessDecision, Rule, decide_access
from usage.identity import VisitorIdentity

IDENTITY = VisitorIdentity("fp-id", "ip-id", "owner-id", 0)


def test_whitelist_takes_precedence_over_blacklist():
    rules = [
        Rule("blacklist", "ip", "203.0.113.8"),
        Rule("whitelist", "fingerprint", "fp-id"),
    ]

    assert decide_access(rules, IDENTITY, "203.0.113.8") is AccessDecision.ALLOW


def test_matching_blacklist_blocks_visitor():
    rules = [Rule("blacklist", "owner", "owner-id")]

    assert decide_access(rules, IDENTITY, "203.0.113.8") is AccessDecision.BLOCK


def test_unmatched_rules_use_default_access():
    rules = [Rule("blacklist", "ip", "198.51.100.2")]

    assert decide_access(rules, IDENTITY, "203.0.113.8") is AccessDecision.DEFAULT
