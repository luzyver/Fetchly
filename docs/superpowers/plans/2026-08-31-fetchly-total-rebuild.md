# Fetchly Total Rebuild Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the current Flask application with a Django 6.1 and HTMX application backed by MongoDB and Redis/RQ while preserving supported providers, temporary downloads, fingerprint-plus-IP history and quotas, CAPTCHA, and staff operations.

**Architecture:** Build one Django codebase split into `downloads`, `providers`, `usage`, and `dashboard` domain apps. Web requests validate and persist intent, RQ workers perform all slow provider/media work, MongoDB stores document-native state, Redis persists queues and coordination, and a shared volume holds expiring media files.

**Tech Stack:** Python 3.13, Django 6.1, official `django-mongodb-backend` 6.1, MongoDB 8, HTMX, Redis 8 with AOF, RQ 2, Gunicorn, Playwright, `yt-dlp`, FFmpeg, pytest, and Docker Compose.

**Spec:** `docs/superpowers/specs/2026-08-31-fetchly-total-rebuild-design.md`

## Global Constraints

- Do not create Git commits unless the user explicitly authorizes commits later; each task ends with a diff and test checkpoint instead.
- Start with an empty MongoDB database; do not migrate SQLite data.
- Preserve support for YouTube, TikTok, X/Twitter, Instagram, Facebook, Vimeo, Dailymotion, Twitch, Bilibili, direct media URLs, and generic Playwright resolution.
- Identify history ownership with fingerprint plus IP; enforce quota against both the fingerprint and IP identifiers.
- Keep resolver cookies, referers, signed media URLs, output paths, and authoritative format data on the server.
- Store downloaded files temporarily and delete them automatically; do not add permanent storage or backups for media.
- Do not include WARP, an outbound proxy service, React, Next.js, user accounts, or a public API.
- Use Indonesian public-facing copy, mobile-first layouts, WCAG-friendly focus/contrast, reduced motion, and 44px minimum touch targets.
- Use WIB (`Asia/Jakarta`) for daily quota boundaries and UTC for persisted timestamps.
- Pin every production dependency to a compatible minor series and generate a reproducible lock file during Task 1.

## Target File Structure

```text
manage.py                         Django command entrypoint
pyproject.toml                    Runtime and development dependencies
fetchly/settings.py               Environment-driven Django configuration
fetchly/urls.py                   Root URL routing
fetchly/rq.py                     Redis/RQ connection and queue helpers
fetchly/worker.py                 Django-aware RQ worker entrypoint
fetchly/logging.py                Structured logging formatter and redaction
downloads/models.py               Task and embedded format documents
downloads/states.py               Valid task state transitions
downloads/services.py             Inspection/download command services
downloads/jobs.py                 RQ job entrypoints and reconciliation
downloads/views.py                Public HTMX task endpoints and file delivery
downloads/urls.py                 Download URL routes
downloads/cleanup.py              File/document retention logic
providers/contracts.py            Typed normalized provider results
providers/registry.py             Provider selection
providers/url_safety.py           SSRF-safe URL and redirect validation
providers/ytdlp.py                Shared yt-dlp inspection/download adapter
providers/tiktok.py               TikTok normalization and audio behavior
providers/twitter.py              X/Twitter multi-video behavior
providers/instagram.py            Instagram-specific behavior
providers/generic.py              Direct and generic yt-dlp providers
providers/resolver.py             Bounded Playwright resolver
usage/models.py                   Daily usage and access-rule documents
usage/identity.py                 IP normalization and HMAC identifiers
usage/quota.py                    Atomic dual-identifier reservations
usage/ratelimit.py                Redis rate limiting
usage/captcha.py                  Cloudflare Turnstile verification
dashboard/views.py                Staff dashboard and access-rule actions
dashboard/urls.py                 Staff routes
templates/                        Base, public fragments, error, and dashboard UI
static/css/app.css                Tokens and responsive component styles
static/js/app.js                  Clipboard, fingerprint, theme, and small UX hooks
tests/                            Unit, integration, worker, and browser tests
Dockerfile                        Single image shared by web and worker
docker-compose.yml                Web, worker, MongoDB, Redis, and smoke topology
scripts/smoke.ps1                 Windows-friendly deployment smoke check
```

The existing Flask files remain untouched until Task 10. New code must not import from `app.py` or `routes/`; reusable provider behavior is ported behind the new provider contract before the old files are removed.

---

### Task 1: Reproducible Django and Container Foundation

**Files:**
- Create: `manage.py`
- Create: `pyproject.toml`
- Create: `fetchly/__init__.py`
- Create: `fetchly/settings.py`
- Create: `fetchly/urls.py`
- Create: `fetchly/wsgi.py`
- Create: `fetchly/rq.py`
- Create: `fetchly/worker.py`
- Create: `tests/test_health.py`
- Create: `tests/conftest.py`
- Modify: `Dockerfile`
- Modify: `docker-compose.yml`
- Modify: `.env.example`

**Interfaces:**
- Produces: Django settings, `fetchly.rq.get_queue(name: str = "media") -> rq.Queue`, a Django-aware RQ worker entrypoint, `/health/live`, and `/health/ready`.
- Consumes: no new application interfaces.

- [ ] **Step 1: Write failing health tests**

```python
# tests/test_health.py
import pytest
from django.urls import reverse


def test_liveness(client):
    response = client.get(reverse("health-live"))
    assert response.status_code == 200
    assert response.json() == {"ok": True}


@pytest.mark.django_db
def test_readiness_reports_dependencies(client, monkeypatch):
    monkeypatch.setattr("fetchly.views.mongo_ready", lambda: True)
    monkeypatch.setattr("fetchly.views.redis_ready", lambda: True)
    monkeypatch.setattr("fetchly.views.downloads_ready", lambda: True)
    response = client.get(reverse("health-ready"))
    assert response.status_code == 200
    assert response.json() == {
        "ok": True,
        "mongodb": True,
        "redis": True,
        "downloads": True,
    }
```

- [ ] **Step 2: Add the pinned project configuration**

Create `pyproject.toml` with Python `>=3.13,<3.14`, runtime dependencies for Django 6.1, matching `django-mongodb-backend`, Redis/RQ, Gunicorn, Playwright, yt-dlp, Requests, cryptography, and development dependencies for pytest, pytest-django, Ruff, and Playwright browser tests. Generate the lock file with the selected package manager and install from that lock in Docker.

Configure `fetchly/settings.py` to require `SECRET_KEY`, `MONGODB_URI`, and `REDIS_URL`; use `django_mongodb_backend`; set `TIME_ZONE = "Asia/Jakarta"`, `USE_TZ = True`, secure proxy/cookie settings from explicit environment flags, and local static/download directories. Do not read environment variables at module import in reusable domain modules.

- [ ] **Step 3: Implement health views and queue factory**

```python
# fetchly/rq.py
from django.conf import settings
from redis import Redis
from rq import Queue


def get_queue(name: str = "media") -> Queue:
    return Queue(name, connection=Redis.from_url(settings.REDIS_URL))
```

```python
# fetchly/worker.py
import os
import django
from rq import Worker

from fetchly.rq import get_queue


def main() -> None:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "fetchly.settings")
    django.setup()
    Worker([get_queue()]).work(with_scheduler=True)


if __name__ == "__main__":
    main()
```

The readiness view must issue `MongoClient.admin.command("ping")`, Redis `ping()`, and a write/delete probe inside `DOWNLOAD_ROOT`; it returns HTTP 503 when any check fails. Liveness must not call dependencies.

- [ ] **Step 4: Replace the container topology**

Use one image for `web` and `worker`. Compose must define `web`, `worker`, `mongodb`, and `redis`; mount one named `downloads` volume into web and worker; enable Redis `appendonly yes`; add health checks; and remove `warp`, `PROXY`, SQLite paths, and the external WARP dependency. Set the worker command exactly to `python -m fetchly.worker`.

- [ ] **Step 5: Verify the foundation**

Run:

```powershell
docker compose config
docker compose up -d mongodb redis
python -m pytest tests/test_health.py -v
python -m ruff check fetchly tests
git diff --check
```

Expected: Compose validates, both dependency containers become healthy, both health tests pass, Ruff reports no errors, and `git diff --check` is silent.

---

### Task 2: Visitor Identity, Access Rules, and Atomic Quotas

**Files:**
- Create: `usage/__init__.py`
- Create: `usage/apps.py`
- Create: `usage/models.py`
- Create: `usage/identity.py`
- Create: `usage/quota.py`
- Create: `usage/ratelimit.py`
- Create: `usage/admin.py`
- Create: `tests/usage/test_identity.py`
- Create: `tests/usage/test_quota.py`
- Create: `tests/usage/test_access_rules.py`
- Create: `tests/usage/conftest.py`
- Modify: `fetchly/settings.py`

**Interfaces:**
- Produces: `VisitorIdentity`; `identity_from_request(request: HttpRequest, fingerprint: str) -> VisitorIdentity`; `reserve_quota(identity: VisitorIdentity, task_token: str, byte_count: int, *, limit_bytes: int, active_limit: int) -> QuotaReservation`; `settle_quota(identity: VisitorIdentity, task_token: str, actual_bytes: int) -> None`; `release_quota(identity: VisitorIdentity, task_token: str, charged_bytes: int = 0) -> None`; `is_blocked(identity: VisitorIdentity, normalized_ip: str) -> bool`; and `hit_rate_limit(bucket: str, identifier: str, limit: int, window_seconds: int) -> bool`.
- Consumes: MongoDB connection from Django and Redis configuration from Task 1.

- [ ] **Step 1: Write identity tests**

```python
# tests/usage/test_identity.py
from usage.identity import build_identity, normalize_ip


def test_identity_is_stable_and_does_not_expose_inputs(settings):
    settings.IDENTITY_HMAC_KEYS = ["test-secret"]
    identity = build_identity("browser-fp", "203.0.113.8")
    assert identity.owner_id == build_identity("browser-fp", "203.0.113.8").owner_id
    assert "browser-fp" not in identity.owner_id
    assert "203.0.113.8" not in identity.ip_id


def test_ipv4_mapped_ipv6_is_normalized():
    assert normalize_ip("::ffff:203.0.113.8") == "203.0.113.8"
```

- [ ] **Step 2: Implement typed HMAC identity**

```python
# usage/identity.py
from dataclasses import dataclass
import hashlib
import hmac
import ipaddress


@dataclass(frozen=True)
class VisitorIdentity:
    fingerprint_id: str
    ip_id: str
    owner_id: str
    key_version: int


def _digest(secret: str, namespace: str, value: str) -> str:
    payload = f"{namespace}:{value}".encode()
    return hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()


def normalize_ip(value: str) -> str:
    address = ipaddress.ip_address(value)
    if address.version == 6 and address.ipv4_mapped:
        return str(address.ipv4_mapped)
    return address.compressed
```

`identity_from_request` must trust `X-Forwarded-For` only when `REMOTE_ADDR` belongs to `TRUSTED_PROXY_NETWORKS`. Reject empty fingerprints on mutation endpoints; public status/download authorization recomputes all configured current/previous owner IDs during secret rotation.

- [ ] **Step 3: Define document-native models and indexes**

Use `ObjectIdAutoField`. `DailyUsage` has `identifier`, `identifier_type`, `day`, `charged_bytes`, `reserved_bytes`, `active_tasks`, and embedded task reservations `{task_token, bytes, created_at}`. Add a unique index on `(identifier, day)`. `AccessRule` has `kind`, `subject_type`, `subject_value`, `note`, `created_by_id`, `created_by_name`, `created_at`, and `updated_at`; add a unique index on `(kind, subject_type, subject_value)`. Store creator snapshots instead of a cross-collection foreign key.

- [ ] **Step 4: Write quota race and compensation tests**

```python
# tests/usage/test_quota.py
import pytest
from usage.quota import QuotaExceeded, reserve_quota


@pytest.mark.django_db(transaction=True)
def test_second_identifier_failure_compensates_first(identity, usage_factory):
    usage_factory(identifier=identity.ip_id, charged_bytes=900, limit_bytes=1_000)
    with pytest.raises(QuotaExceeded):
        reserve_quota(identity, "task-a", 200, limit_bytes=1_000, active_limit=1)
    fingerprint_usage = usage_factory.get(identity.fingerprint_id)
    assert fingerprint_usage.reserved_bytes == 0
    assert fingerprint_usage.active_tasks == 0
```

Add a concurrency test that launches two 700-byte reservations against a 1,000-byte limit and asserts exactly one succeeds.

Define `tests/usage/conftest.py` fixtures explicitly: `identity` returns `VisitorIdentity("fp-id", "ip-id", "owner-id", 0)`; `usage_factory` creates/reads `DailyUsage` documents through a small callable fixture with `.get(identifier)` so the test above performs real MongoDB writes rather than mocks.

- [ ] **Step 5: Implement fail-closed reservation services**

Use conditional `QuerySet.update()` or a raw MongoDB update pipeline so `charged_bytes + reserved_bytes + requested <= limit` and `active_tasks < active_limit` are checked in the same write for each identifier. Store the task token in each reservation. Reserve fingerprint first, then IP; compensate fingerprint if IP fails. Settlement converts only that task's reservation to actual charged bytes. Reconciliation removes reservations whose task token no longer exists or has passed the stale threshold.

- [ ] **Step 6: Implement Redis fixed-window limits**

Use one Redis transaction: `INCR` a namespaced key and set `EXPIRE` only when the result is one. Return `True` only when the incremented count exceeds the configured limit. Cover independent buckets for inspect, download, status, file, and admin login.

- [ ] **Step 7: Verify usage behavior**

Run:

```powershell
python -m pytest tests/usage -v
python -m ruff check usage tests/usage
git diff --check
```

Expected: identity, access-rule, quota compensation, concurrency, settlement, and rate-limit tests pass.

---

### Task 3: SSRF-Safe Provider Contract and Registry

**Files:**
- Create: `providers/__init__.py`
- Create: `providers/apps.py`
- Create: `providers/contracts.py`
- Create: `providers/errors.py`
- Create: `providers/url_safety.py`
- Create: `providers/registry.py`
- Create: `tests/providers/test_url_safety.py`
- Create: `tests/providers/test_registry.py`
- Create: `tests/providers/test_contracts.py`
- Modify: `fetchly/settings.py`

**Interfaces:**
- Produces: `MediaFormat`, `InspectionResult`, `ResolvedMedia`, `DownloadRequest`, `DownloadResult`, `ValidatedUrl`, `Provider` protocol, `validate_public_url(url: str) -> ValidatedUrl`, and `get_provider(url: str) -> Provider`.
- Consumes: configuration from Task 1.

- [ ] **Step 1: Define contract tests**

```python
# tests/providers/test_contracts.py
from providers.contracts import MediaFormat


def test_public_format_dict_excludes_sensitive_fields():
    value = MediaFormat(
        id="720p",
        label="720p",
        extension="mp4",
        kind="video",
        height=720,
        estimated_bytes=12_000,
    )
    assert value.to_public_dict() == {
        "id": "720p",
        "label": "720p",
        "extension": "mp4",
        "kind": "video",
        "height": 720,
        "estimated_bytes": 12_000,
    }
```

Use frozen dataclasses with explicit fields. `InspectionResult` contains provider, canonical URL, title, thumbnail URL, duration seconds, tuple of formats, and opaque resolver context. Only `to_public_dict()` output may reach templates.

- [ ] **Step 2: Write SSRF tests**

Cover `http`/`https`, credentials in authority, malformed hosts, `localhost`, IPv4/IPv6 loopback, private, link-local, carrier-grade NAT, multicast, unspecified addresses, decimal/hex IP forms, DNS answers containing any nonpublic address, redirects to private addresses, and public HTTPS success. Mock DNS deterministically.

- [ ] **Step 3: Implement URL validation**

```python
# providers/url_safety.py
from dataclasses import dataclass
import ipaddress
import socket
from urllib.parse import urlsplit


class UnsafeUrl(ValueError):
    pass


def _is_public(address: str) -> bool:
    ip = ipaddress.ip_address(address)
    return ip.is_global and not any((ip.is_private, ip.is_loopback, ip.is_link_local, ip.is_multicast, ip.is_unspecified))
```

`validate_public_url` must reject userinfo, non-HTTP schemes, missing hostnames, disallowed ports, and any DNS result that is not public. Return a normalized URL and a tuple of validated IP addresses. The HTTP client/provider must validate every redirect target again and connect with bounded timeouts. Playwright route interception must apply the same rule to document/iframe navigation.

- [ ] **Step 4: Implement provider registry**

Define one ordered registry that maps normalized host suffixes to provider instances. Match exact hosts or `.<domain>` suffixes so `notyoutube.com` cannot match `youtube.com`. Direct media extensions are checked after safe URL validation. Unknown public URLs select the generic resolver provider.

- [ ] **Step 5: Verify security boundaries**

Run:

```powershell
python -m pytest tests/providers/test_url_safety.py tests/providers/test_registry.py tests/providers/test_contracts.py -v
python -m ruff check providers tests/providers
git diff --check
```

Expected: all unsafe URL classes are rejected, public mocked hosts pass, registry routing is exact, and public serialization contains no resolver context.

---

### Task 4: Port Specialized, yt-dlp, and Generic Providers

**Files:**
- Create: `providers/ytdlp.py`
- Create: `providers/youtube.py`
- Create: `providers/tiktok.py`
- Create: `providers/twitter.py`
- Create: `providers/instagram.py`
- Create: `providers/generic.py`
- Create: `tests/providers/fixtures/*.json`
- Create: `tests/providers/test_ytdlp.py`
- Create: `tests/providers/test_specialized.py`
- Create: `tests/providers/test_generic.py`
- Read for porting: `core/youtube.py`
- Read for porting: `core/tiktok.py`
- Read for porting: `core/twitter.py`
- Read for porting: `core/instagram.py`
- Read for porting: `core/generic.py`
- Read for porting: `core/utils.py`

**Interfaces:**
- Produces: provider classes implementing `inspect(url: str) -> InspectionResult` and `download(request: DownloadRequest) -> DownloadResult`.
- Consumes: contracts, errors, and safe URLs from Task 3.

- [ ] **Step 1: Capture sanitized fixtures and expected normalized results**

Create one fixture for each provider family using existing test-safe metadata or manually minimized samples. Remove cookies, signatures, tokens, user IDs, and live expiring media URLs. Each fixture must contain enough format metadata to assert friendly presets, audio-only behavior, estimated size, multi-video X behavior, and absent-size handling.

- [ ] **Step 2: Write shared adapter tests**

```python
# tests/providers/test_ytdlp.py
from providers.ytdlp import build_download_args


def test_download_args_are_fixed_and_size_limited(tmp_path):
    args = build_download_args(
        url="https://media.example/video",
        format_selector="18",
        output_path=tmp_path / "result.mp4",
        max_bytes=10_000_000,
        referer="https://media.example/",
    )
    assert args[0] == "yt-dlp"
    assert "--max-filesize" in args
    assert "10M" in args
    assert "shell=True" not in args
```

Also assert no call uses forced recoding that can bypass size monitoring, stderr is capped/redacted, subprocess timeouts are mandatory, and partial files are reported for cleanup.

- [ ] **Step 3: Implement the shared yt-dlp boundary**

Use `subprocess.Popen` with an argument list and `shell=False`. Stream-monitor all files matching the task-specific basename once per second; kill the process group when the limit or timeout is exceeded. Normalize errors to stable codes: `private`, `unavailable`, `authentication_required`, `rate_limited`, `timeout`, `too_large`, and `provider_failed`.

- [ ] **Step 4: Port provider behavior behind contracts**

Port only provider-specific extraction and format normalization from the existing modules. YouTube and the general supported sites use the shared yt-dlp adapter. TikTok preserves no-watermark and audio choices. X/Twitter preserves multi-video labeling. Instagram preserves its authenticated-cookie behavior when configured. No provider writes task rows or quota data.

- [ ] **Step 5: Test every provider against the same assertions**

Parametrize fixture tests over every provider and assert nonempty title, stable provider key, unique format IDs, allowed extensions, friendly labels, no secrets in public dictionaries, and a valid download request for every offered format.

- [ ] **Step 6: Verify provider parity**

Run:

```powershell
python -m pytest tests/providers/test_ytdlp.py tests/providers/test_specialized.py tests/providers/test_generic.py -v
python -m ruff check providers tests/providers
git diff --check
```

Expected: every supported provider fixture satisfies the shared contract and subprocess safety tests pass without network access.

---

### Task 5: Bounded Playwright Resolver

**Files:**
- Create: `providers/resolver.py`
- Create: `tests/providers/test_resolver.py`
- Read for porting: `core/resolver.py`

**Interfaces:**
- Produces: `resolve_media(url: str, limits: ResolverLimits) -> ResolvedMedia`.
- Consumes: `validate_public_url`, provider contracts, and provider errors from Task 3.

- [ ] **Step 1: Write resolver-bound tests**

Use mocked Playwright pages/routes to assert maximum pages/iframes visited, maximum captured URLs, overall deadline, context closure after success/failure, blocked private iframe navigation, media content-type detection, deduplication, and no domain-wide cache reuse of signed media URLs.

```python
def test_private_iframe_is_aborted(fake_page, resolver_limits):
    fake_page.add_iframe("http://127.0.0.1/admin")
    result = resolve_media("https://public.example/watch/1", resolver_limits)
    assert result is None
    assert fake_page.aborted_urls == ["http://127.0.0.1/admin"]
```

- [ ] **Step 2: Implement explicit resolver limits**

Define `ResolverLimits(max_pages=8, max_iframes=12, max_captured_urls=100, navigation_seconds=30, overall_seconds=45)`. Use one browser process per worker and one isolated context per task. Close every context in `finally`. Keep only a short URL-keyed inspection cache; do not cache one media result for an entire domain.

- [ ] **Step 3: Apply safety checks at every navigation boundary**

Validate initial URL, redirected page URL, iframe source, captured manifest/media URL, and manifest child URLs. Abort requests to nonpublic destinations and resource types unrelated to discovery (fonts and large images) while allowing scripts, documents, XHR/fetch, and media.

- [ ] **Step 4: Verify resolver behavior**

Run:

```powershell
python -m pytest tests/providers/test_resolver.py -v
python -m ruff check providers/resolver.py tests/providers/test_resolver.py
git diff --check
```

Expected: all resource bounds and SSRF assertions pass and every fake browser context closes.

---

### Task 6: Download Task Model, State Machine, Jobs, and File Authorization

**Files:**
- Create: `downloads/__init__.py`
- Create: `downloads/apps.py`
- Create: `downloads/models.py`
- Create: `downloads/states.py`
- Create: `downloads/services.py`
- Create: `downloads/jobs.py`
- Create: `downloads/views.py`
- Create: `downloads/urls.py`
- Create: `downloads/crypto.py`
- Create: `tests/downloads/test_states.py`
- Create: `tests/downloads/test_services.py`
- Create: `tests/downloads/test_jobs.py`
- Create: `tests/downloads/test_views.py`
- Modify: `fetchly/urls.py`
- Modify: `fetchly/settings.py`

**Interfaces:**
- Produces: `create_inspection(identity: VisitorIdentity, url: str) -> str`; `request_download(identity: VisitorIdentity, token: str, format_id: str) -> None`; `inspect_task(task_id: str) -> None`; `download_task(task_id: str) -> None`; `reconcile_stale_tasks(now: datetime) -> ReconcileResult`; and owner-authorized status/file views.
- Consumes: identity/quota/rate-limit interfaces from Task 2 and provider interfaces from Tasks 3–5.

- [ ] **Step 1: Write state-machine tests**

```python
# tests/downloads/test_states.py
import pytest
from downloads.states import InvalidTransition, TaskState, transition


def test_download_happy_path():
    state = TaskState.INSPECTION_QUEUED
    for target in (
        TaskState.INSPECTING,
        TaskState.READY,
        TaskState.DOWNLOAD_QUEUED,
        TaskState.DOWNLOADING,
        TaskState.COMPLETED,
    ):
        state = transition(state, target)
    assert state is TaskState.COMPLETED


def test_completed_cannot_return_to_downloading():
    with pytest.raises(InvalidTransition):
        transition(TaskState.COMPLETED, TaskState.DOWNLOADING)
```

- [ ] **Step 2: Implement task documents and transition service**

`DownloadTask` uses an `ObjectIdAutoField` internally and a unique 256-bit URL-safe public token. Store owner/fingerprint/IP HMAC IDs, provider metadata, embedded public formats, encrypted resolver context, state, progress summary, retry count, safe error code, internal redacted detail, timestamps, task directory, output file, size, and expiry. Index owner plus created time, state plus updated time, public token, and expiry.

Encryption uses Fernet/MultiFernet keys from `RESOLVER_ENCRYPTION_KEYS`; decrypted context exists only within worker memory and is erased from the document after terminal state.

- [ ] **Step 3: Write command-service tests**

Test that inspection rejects missing fingerprints, unsafe URLs, blocked visitors, and exhausted rate limits before queueing. Test that download submission rejects wrong owners, expired inspection, unknown format IDs, a second active job, and exhausted quota. Assert the queue receives only the internal MongoDB task ID, never cookies or URLs.

- [ ] **Step 4: Implement command services**

`create_inspection` creates `inspection_queued`, enqueues `downloads.jobs.inspect_task`, and returns the public token. `request_download` loads the server-owned format snapshot, reserves quota, sets `download_queued`, and enqueues `downloads.jobs.download_task`. Use compare-and-update filters containing the expected current state so duplicate requests cannot enqueue duplicate work.

- [ ] **Step 5: Implement worker jobs**

`inspect_task` claims only `inspection_queued`, validates the URL again, invokes the registry, encrypts private resolver context, stores public format snapshots, and transitions to `ready`. `download_task` claims only `download_queued`, creates a directory named from the internal task ID below `DOWNLOAD_ROOT`, invokes the provider, settles or releases quota, clears resolver context, and transitions to a terminal state. Always clean partial files after exceptions.

Retry only stable transient error codes with exponential intervals and a maximum of two retries. On retry exhaustion, set `failed` and release reservations.

- [ ] **Step 6: Implement owner-authorized endpoints**

Routes:

```text
POST /tasks/inspect
GET  /tasks/<token>/inspection
POST /tasks/<token>/download
GET  /tasks/<token>/status
GET  /tasks/<token>/file
```

Every route except initial inspection recomputes owner candidates from fingerprint cookie plus current request IP and performs a constant-time signed-token check before querying. Status/inspection endpoints return HTMX fragments. File delivery requires `completed`, unexpired metadata, and a resolved path strictly below `DOWNLOAD_ROOT`; set `Content-Disposition`, `X-Content-Type-Options: nosniff`, and `Cache-Control: private, no-store`.

- [ ] **Step 7: Verify jobs and authorization**

Run:

```powershell
python -m pytest tests/downloads -v
python -m ruff check downloads tests/downloads
git diff --check
```

Expected: state, idempotency, encryption, retry, quota settlement, path traversal, ownership, and file-expiry tests pass.

---

### Task 7: Public HTMX Experience, History, CAPTCHA, and Accessibility

**Files:**
- Create: `templates/base.html`
- Create: `templates/downloads/index.html`
- Create: `templates/downloads/_inspection.html`
- Create: `templates/downloads/_formats.html`
- Create: `templates/downloads/_status.html`
- Create: `templates/downloads/_history.html`
- Create: `templates/errors/403.html`
- Create: `templates/errors/404.html`
- Create: `templates/errors/405.html`
- Create: `static/css/app.css`
- Create: `static/js/app.js`
- Create: `usage/captcha.py`
- Create: `downloads/history.py`
- Create: `tests/browser/test_public_flow.py`
- Create: `tests/browser/conftest.py`
- Create: `tests/usage/test_captcha.py`
- Modify: `downloads/views.py`
- Modify: `downloads/urls.py`

**Interfaces:**
- Produces: public homepage, HTMX fragments, versioned browser fingerprint cookie, CAPTCHA validation, and current-owner history.
- Consumes: task endpoints from Task 6 and identity/rate-limit services from Task 2.

- [ ] **Step 1: Write browser journey tests**

```python
# tests/browser/test_public_flow.py
def test_mobile_paste_to_ready_download(page, live_server, fake_media_worker):
    page.set_viewport_size({"width": 390, "height": 844})
    page.goto(live_server.url)
    page.get_by_label("Tautan video").fill("https://video.example/watch/1")
    page.get_by_role("button", name="Cari format").click()
    page.get_by_role("radio", name="Video terbaik").check()
    page.get_by_role("button", name="Siapkan unduhan").click()
    assert page.get_by_role("status").get_by_text("Siap diunduh").is_visible()
    assert page.get_by_role("link", name="Unduh sekarang").is_visible()
```

Add journeys for invalid URL, private media, CAPTCHA failure, quota exhausted, expired file, keyboard-only format selection, `prefers-reduced-motion`, dark color scheme, and history visibility only for the same owner.

Define `tests/browser/conftest.py` so `live_server` starts Django with test MongoDB/Redis settings and `fake_media_worker` drains queued jobs synchronously using a deterministic provider that returns one video format and writes a small fixture file below `DOWNLOAD_ROOT`. The fixture must restore the real provider registry and RQ enqueue behavior after each test.

- [ ] **Step 2: Implement page and fragment semantics**

Use a single `<main>` flow with a labeled URL input, explicit submit buttons, field-level errors, and `aria-live="polite"` status region. HTMX polling starts only while a task is nonterminal and stops when `ready`, `completed`, `failed`, `blocked`, or `expired`. Format cards are real radio inputs. Advanced technical details use `<details>`.

- [ ] **Step 3: Implement the playful design system**

Define CSS custom properties for background, surface, ink, muted ink, primary, accent, success, warning, danger, radius, shadow, and spacing. Provide light/dark variables through `prefers-color-scheme`. Use grid/flex without horizontal page scrolling, reserve media/alert space to avoid layout shift, enforce 44px controls, and disable nonessential animation under `prefers-reduced-motion: reduce`.

Do not load Tailwind or scripts from a CDN. Vendor the pinned HTMX asset under `static/vendor/` with its license and integrity recorded in project documentation.

- [ ] **Step 4: Implement minimal browser JavaScript**

`static/js/app.js` owns only clipboard paste, a versioned fingerprint stored in a secure same-site cookie via a server endpoint, theme preference override, and focus restoration after HTMX swaps. Do not recreate request, state, rendering, or polling layers in JavaScript.

- [ ] **Step 5: Implement Turnstile verification**

When both Turnstile keys are configured, render the widget and verify tokens server-side with a five-second timeout and the visitor IP. Fail closed on inspect/download mutations. When keys are absent in development/test, omit the widget and return an explicit disabled result; production startup checks reject a half-configured pair.

- [ ] **Step 6: Implement owner history**

Query the 20 most recent tasks by current owner ID. Return only title, provider, public state, safe error message, size, timestamps, expiry, and authorized action URLs. Do not return source/resolved URLs, internal IDs, visitor identifiers, paths, or resolver context.

- [ ] **Step 7: Verify public UX**

Run:

```powershell
python -m pytest tests/usage/test_captcha.py tests/browser/test_public_flow.py -v
python -m ruff check usage downloads tests
git diff --check
```

Expected: all journeys pass at mobile and desktop sizes, no unauthorized history/file is visible, and reduced-motion/dark-mode assertions pass.

---

### Task 8: Staff Dashboard and Audited Access Rules

**Files:**
- Create: `dashboard/__init__.py`
- Create: `dashboard/apps.py`
- Create: `dashboard/urls.py`
- Create: `dashboard/views.py`
- Create: `dashboard/forms.py`
- Create: `templates/dashboard/base.html`
- Create: `templates/dashboard/index.html`
- Create: `templates/dashboard/_tasks.html`
- Create: `templates/dashboard/_access_rules.html`
- Create: `templates/registration/login.html`
- Create: `tests/dashboard/test_auth.py`
- Create: `tests/dashboard/test_views.py`
- Modify: `fetchly/urls.py`
- Modify: `fetchly/settings.py`

**Interfaces:**
- Produces: `/admin/login/`, `/admin/`, task filters, metrics summaries, and CSRF-protected access-rule mutations.
- Consumes: Django authentication, download documents from Task 6, usage documents from Task 2, and queue health from Task 1.

- [ ] **Step 1: Write dashboard authorization tests**

Assert anonymous users redirect to login, inactive/nonstaff users receive 403, staff sessions expire at the configured age, login rate limits are IP-scoped, CSRF is required for mutations, and internal task fields never occur in rendered HTML.

- [ ] **Step 2: Write dashboard behavior tests**

Create task/usage fixtures and assert counts by state, success rate, provider duration aggregates, queue depth, oldest job age, storage usage, masked visitor identifiers, pagination, provider/state/date search filters, and access-rule creation/removal audit metadata.

- [ ] **Step 3: Implement staff-only views and forms**

Wrap every dashboard view with `staff_member_required`. Use validated Django forms for rule kind, subject type, subject value, and note. Normalize IP/CIDR input and hash fingerprint input through the identity service. All add/remove actions use POST and redirect or return an HTMX fragment; no mutation uses GET or DELETE from browser JavaScript.

- [ ] **Step 4: Implement operational templates**

Reuse public design tokens with denser tables/cards. Include accessible labels, empty/loading/error states, sticky table headings only where they do not obscure content, and confirmation dialogs based on native `<dialog>`. Mask IPs and identifiers by default. Never render cookies, referers, resolved URLs, encryption payloads, output paths, or full stderr.

- [ ] **Step 5: Verify dashboard behavior**

Run:

```powershell
python -m pytest tests/dashboard -v
python -m ruff check dashboard tests/dashboard
git diff --check
```

Expected: auth, session, CSRF, redaction, aggregates, filtering, and rule audit tests pass.

---

### Task 9: Cleanup, Reconciliation, Logging, and Capability Health

**Files:**
- Create: `downloads/cleanup.py`
- Create: `fetchly/logging.py`
- Create: `downloads/management/commands/reconcile_downloads.py`
- Create: `downloads/management/commands/check_capabilities.py`
- Create: `tests/downloads/test_cleanup.py`
- Create: `tests/test_logging.py`
- Create: `tests/test_capabilities.py`
- Modify: `downloads/jobs.py`
- Modify: `fetchly/settings.py`
- Modify: `docker-compose.yml`

**Interfaces:**
- Produces: `cleanup_expired(now: datetime) -> CleanupResult`, `reconcile_stale_tasks(now: datetime) -> ReconcileResult`, structured/redacted JSON logs, worker heartbeat, and staff capability health.
- Consumes: task states from Task 6, quota release from Task 2, and runtime binaries from Task 1.

- [ ] **Step 1: Write retention and reconciliation tests**

Cover deletion of expired completed files, failed partial files, missing completed files changing to `expired`, stale inspection/download jobs, stale quota reservations, path escape refusal, repeated cleanup idempotency, and preservation of unexpired files.

- [ ] **Step 2: Implement safe cleanup**

Resolve every candidate path and require `candidate.is_relative_to(DOWNLOAD_ROOT.resolve())` before unlinking. Delete files first, then update documents. Terminal task cleanup is idempotent. Reconciliation requeues only tasks with retry budget and no live RQ job; otherwise it fails them with `worker_interrupted` and releases reservations.

- [ ] **Step 3: Write redaction tests**

```python
# tests/test_logging.py
from fetchly.logging import redact


def test_redact_removes_sensitive_query_and_headers():
    value = redact({
        "url": "https://cdn.example/video?token=secret&x=1",
        "cookies": "session=secret",
        "authorization": "Bearer secret",
    })
    assert "secret" not in str(value)
    assert value["url"] == "https://cdn.example/video"
```

- [ ] **Step 4: Implement structured logging and health**

Emit JSON fields `timestamp`, `level`, `logger`, `message`, `request_id`, `task_id`, `provider`, `state`, `elapsed_ms`, and `error_code`. Apply redaction before formatting. Middleware generates/accepts only valid request IDs. Worker heartbeat is a Redis key with expiry. Capability checks run `ffmpeg -version`, `yt-dlp --version`, and a minimal Playwright browser launch with strict timeouts; detailed results require staff access.

- [ ] **Step 5: Schedule cleanup and heartbeats**

Register cleanup/reconciliation through the RQ scheduler at a fixed interval shorter than file retention. Compose health checks must fail when web readiness fails or worker heartbeat expires, without invoking external media sites.

- [ ] **Step 6: Verify operational behavior**

Run:

```powershell
python -m pytest tests/downloads/test_cleanup.py tests/test_logging.py tests/test_capabilities.py -v
python manage.py check_capabilities
python -m ruff check fetchly downloads tests
git diff --check
```

Expected: cleanup is idempotent and path-safe, secrets are redacted, and installed media capabilities report healthy.

---

### Task 10: Full Verification and Flask Cutover

**Files:**
- Create: `scripts/smoke.ps1`
- Create: `README.md`
- Create: `tests/test_no_legacy_imports.py`
- Delete after parity passes: `app.py`
- Delete after parity passes: `routes/`
- Delete after parity passes: `core/`
- Delete after parity passes: `templates/index.html`
- Delete after parity passes: `templates/admin_login.html`
- Delete after parity passes: `templates/admin_dashboard.html`
- Delete after parity passes: `templates/403.html`
- Delete after parity passes: `templates/404.html`
- Delete after parity passes: `templates/405.html`
- Delete after parity passes: `templates/devtools.html`
- Delete after parity passes: `static/js/modules/`
- Delete after parity passes: `static/js/admin/`
- Delete after parity passes: `static/js/protection.js`
- Delete after parity passes: `static/js/toast.js`
- Delete after parity passes: `static/css/styles.css`
- Delete after parity passes: `requirements.txt`
- Modify: `.gitignore`

**Interfaces:**
- Produces: one supported Django application and documented deployment/runbook.
- Consumes: every interface and test suite from Tasks 1–9.

- [ ] **Step 1: Add legacy isolation and feature-parity tests**

`tests/test_no_legacy_imports.py` walks Python files outside ignored virtual environments and fails if a new Django module imports `app`, `routes`, or `core`. Add a parity matrix test/fixture that lists every required provider and capability from the spec and asserts each is registered or routed.

- [ ] **Step 2: Write the Docker smoke script**

`scripts/smoke.ps1` must:

1. run `docker compose config`;
2. build images with no cache-sensitive secrets in build arguments;
3. start MongoDB and Redis and wait for health;
4. start web and worker and wait for readiness/heartbeat;
5. run Django system checks and the synthetic local-media worker job;
6. request the homepage and public liveness endpoint;
7. print container status and relevant redacted logs on failure;
8. exit nonzero on any failed step.

The synthetic job uses a generated local test video mounted in the worker and never calls an external site.

- [ ] **Step 3: Document operation and recovery**

README must include required environment variables, secret generation, MongoDB/Redis persistence, first staff-user creation, startup, update procedure, health checks, log fields, retention, backup scope, worker recovery, provider live-smoke procedure, and the explicit statement that WARP/proxy support and SQLite migration are absent.

- [ ] **Step 4: Run the complete verification gate before deleting Flask**

Run:

```powershell
python -m pytest -v
python -m ruff check .
python manage.py check --deploy
pwsh -File scripts/smoke.ps1
git diff --check
```

Expected: every test passes, Django deploy checks contain no unaccepted warnings, Docker smoke succeeds, web/worker/dependency health is green, and the synthetic file expires through cleanup.

- [ ] **Step 5: Remove the legacy Flask application**

Only after Step 4 passes, delete the listed legacy files. Preserve any static asset only if a new Django template references it and its role is documented. Remove Flask and SQLite dependencies/configuration. Do not delete runtime data directories or user-owned `.env` files.

- [ ] **Step 6: Run the final post-deletion gate**

Run:

```powershell
python -m pytest -v
python -m ruff check .
python manage.py check --deploy
pwsh -File scripts/smoke.ps1
rg -n "Flask|sqlite|tasks\.db|PROXY|warp|cdn\.tailwindcss\.com" --glob '!docs/superpowers/**' .
git status --short
git diff --check
```

Expected: tests and smoke pass; the search returns no runtime references to Flask, SQLite, WARP/proxy configuration, or runtime Tailwind CDN; Git shows only the intentional rebuild changes and no commit has been created.

## Execution Order and Review Gates

1. Tasks 1–3 establish the runtime, identity/quota invariants, and SSRF boundary. Review security and data consistency before provider work.
2. Tasks 4–6 establish provider parity and the complete durable task flow. Review with fixture and worker tests before UI work.
3. Tasks 7–8 deliver public and staff experiences. Review with browser tests at mobile and desktop sizes.
4. Task 9 adds production cleanup and observability. Review failure/recovery evidence.
5. Task 10 is the only task authorized to delete legacy code, and only after its pre-deletion verification gate passes.

No task may skip its failing-test step, pass verification by weakening an assertion, or delete legacy code early. Any newly discovered provider behavior must first be captured in a sanitized fixture and a failing contract test.
