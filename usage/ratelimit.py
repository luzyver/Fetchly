_INCREMENT_WITH_EXPIRY = """
local current = redis.call('INCR', KEYS[1])
if current == 1 then
    redis.call('EXPIRE', KEYS[1], ARGV[1])
end
return current
"""


def hit_rate_limit(
    client,
    bucket: str,
    identifier: str,
    limit: int,
    window_seconds: int,
) -> bool:
    if limit < 1 or window_seconds < 1:
        raise ValueError("Rate limit and window must be positive")
    key = f"fetchly:limit:{bucket}:{identifier}"
    current = client.eval(_INCREMENT_WITH_EXPIRY, 1, key, window_seconds)
    return int(current) > limit
