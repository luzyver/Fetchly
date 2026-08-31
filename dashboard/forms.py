import ipaddress
import re

from django import forms

from usage.identity import build_identity


class AccessRuleForm(forms.Form):
    kind = forms.ChoiceField(
        label="Jenis",
        choices=(("whitelist", "Izinkan"), ("blacklist", "Blokir")),
    )
    subject_type = forms.ChoiceField(
        label="Subjek",
        choices=(
            ("fingerprint", "Fingerprint"),
            ("ip", "IP / CIDR"),
            ("ip_hash", "Hash IP"),
            ("owner", "ID pemilik"),
        ),
    )
    subject_value = forms.CharField(label="Nilai", max_length=128)
    note = forms.CharField(label="Catatan", max_length=255, required=False)

    def clean_subject_value(self):
        value = self.cleaned_data["subject_value"].strip()
        subject_type = self.cleaned_data.get("subject_type")
        if subject_type == "ip":
            return str(ipaddress.ip_network(value, strict=False))
        if subject_type == "fingerprint":
            return build_identity(value, "0.0.0.0").fingerprint_id
        if subject_type in {"ip_hash", "owner"} and not re.fullmatch(r"[0-9a-f]{64}", value):
            raise forms.ValidationError("Gunakan hash 64 karakter yang valid.")
        return value
