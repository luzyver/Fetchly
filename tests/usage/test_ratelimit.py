from usage.ratelimit import hit_rate_limit


class FakeRedis:
    def __init__(self):
        self.counts: dict[str, int] = {}
        self.expiry: dict[str, int] = {}

    def eval(self, script: str, key_count: int, key: str, window_seconds: int) -> int:
        self.counts[key] = self.counts.get(key, 0) + 1
        if self.counts[key] == 1:
            self.expiry[key] = window_seconds
        return self.counts[key]


def test_limit_is_exceeded_only_after_allowed_count():
    client = FakeRedis()

    assert hit_rate_limit(client, "inspect", "visitor", 2, 60) is False
    assert hit_rate_limit(client, "inspect", "visitor", 2, 60) is False
    assert hit_rate_limit(client, "inspect", "visitor", 2, 60) is True
    assert client.expiry["fetchly:limit:inspect:visitor"] == 60


def test_buckets_are_independent():
    client = FakeRedis()

    assert hit_rate_limit(client, "inspect", "visitor", 1, 60) is False
    assert hit_rate_limit(client, "download", "visitor", 1, 60) is False
