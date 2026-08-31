from dashboard.forms import AccessRuleForm
from usage.identity import build_identity


def test_raw_fingerprint_is_hashed_before_storage():
    form = AccessRuleForm(
        data={
            "kind": "blacklist",
            "subject_type": "fingerprint",
            "subject_value": "browser-fingerprint",
            "note": "spam",
        }
    )

    assert form.is_valid(), form.errors
    assert (
        form.cleaned_data["subject_value"]
        == build_identity("browser-fingerprint", "0.0.0.0").fingerprint_id
    )


def test_ip_rule_is_normalized_to_cidr():
    form = AccessRuleForm(
        data={
            "kind": "whitelist",
            "subject_type": "ip",
            "subject_value": "192.0.2.8",
            "note": "office",
        }
    )

    assert form.is_valid(), form.errors
    assert form.cleaned_data["subject_value"] == "192.0.2.8/32"
