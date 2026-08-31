# Fetchly Total Rebuild Design

Date: 2026-08-31
Status: Approved in conversation; awaiting written-spec review

## 1. Purpose

Rebuild Fetchly as a modern, reliable, and approachable public media downloader while preserving its useful behavior:

- no user accounts;
- identity, history, and quotas based on browser fingerprint plus IP address;
- support for YouTube, TikTok, X/Twitter, Instagram, Facebook, Vimeo, Dailymotion, Twitch, Bilibili, direct media URLs, and generic sites resolved through a browser;
- format selection, asynchronous conversion, temporary downloads, usage history, CAPTCHA, quotas, whitelist, blacklist, and an operator dashboard;
- temporary files expire and are deleted, as in the current application.

The rebuild starts with an empty database. Existing SQLite data is not migrated.

## 2. Goals

1. Make the public flow understandable to nontechnical users on mobile and desktop.
2. Ensure web-process restarts do not lose queued or active work.
3. Keep sensitive resolver state and media URLs on the server.
4. Make provider failures observable and isolated.
5. Support an initially unknown workload on one VPS and leave a clear scaling path.
6. Keep deployment and maintenance smaller than a microservice architecture.

## 3. Non-goals

- User registration, social login, or cross-device account history.
- Migration of old tasks, quota records, whitelist entries, or blacklist entries.
- Permanent media storage, backup of downloaded files, or a user media library.
- WARP, an outbound proxy container, or proxy-specific application configuration.
- A public third-party API, native mobile application, or multi-region deployment.
- React, Next.js, a separate frontend server, or speculative service decomposition.

## 4. Technology

- Python and Django 6.1 for the web application, templates, forms, CSRF protection, admin authentication, and management commands.
- HTMX for server-rendered interactions and polling; small, framework-free JavaScript modules only where browser APIs are required, such as clipboard access and fingerprint generation.
- Custom compiled CSS with design tokens. No runtime CSS CDN is used.
- MongoDB through the official `django-mongodb-backend` package. The backend package version must match the Django minor release.
- Redis with append-only persistence and RQ for durable asynchronous jobs.
- `yt-dlp`, FFmpeg, and Playwright for media inspection, download, conversion, and generic resolution.
- Gunicorn for Django and Docker Compose for the initial deployment.

The data model avoids relational joins and unsupported ORM behavior. Documents embed snapshots when data is owned by one aggregate. Cross-document transactions are not required for normal application flows.

## 5. Application boundaries

The project is one Django codebase with four domain applications.

### `downloads`

Owns URL inspection, server-side format snapshots, download-task state, status fragments, file authorization, and file responses.

### `providers`

Defines one shared provider result contract and implementations for YouTube, TikTok, Instagram, X/Twitter, direct/generic sources, and the remaining supported sites. It owns Playwright-based resolution and wraps `yt-dlp`/FFmpeg execution. Provider-specific failures cannot leak provider response bodies or credentials to users.

### `usage`

Owns visitor identifiers, daily byte accounting, active-job limits, rate limits, history lookup, whitelist, and blacklist rules.

### `dashboard`

Provides staff-only operational pages using Django authentication. It owns statistics, task search, queue visibility, storage status, and access-rule management. It does not duplicate Django's authentication system.

Modules communicate through explicit service functions and typed value objects. Views do not invoke `yt-dlp`, FFmpeg, or Playwright directly.

## 6. Deployment topology

The initial Docker Compose deployment contains:

- `web`: Django/Gunicorn;
- `worker`: RQ workers running provider and download jobs;
- `mongodb`: primary application data store;
- `redis`: job queue, short-lived rate-limit state, and coordination;
- shared temporary download volume mounted by `web` and `worker`.

Outbound provider requests go directly to their destinations. The existing WARP service and `PROXY` configuration are removed.

The first deployment targets one VPS. MongoDB and Redis connection strings are environment-controlled so either can later move to a managed service. Horizontal media workers require shared object storage and are deferred until observed demand justifies it.

## 7. Data model

All application documents use `ObjectId` primary keys and explicit UTC timestamps. Required lookup paths receive indexes.

### `download_tasks`

Stores:

- public opaque task token;
- HMAC owner key derived from fingerprint plus IP;
- separate HMAC fingerprint and IP identifiers for quota lookup;
- normalized source URL and provider;
- title, thumbnail, duration, and selected format snapshot;
- encrypted, short-lived resolver context when required;
- state, progress summary, retry count, structured error code, and internal error detail;
- temporary file path, file size, expiry time, and lifecycle timestamps.

Allowed states are `inspection_queued`, `inspecting`, `ready`, `download_queued`, `downloading`, `completed`, `failed`, `blocked`, `expired`, and `cancelled`. State changes are validated by one transition service.

### `daily_usage`

One document represents one hashed identifier for one WIB calendar date. It stores identifier type, charged bytes, reserved bytes, task-scoped reservations, active task count, and timestamps. Unique indexing on identifier plus date prevents duplicates. Atomic conditional updates reserve quota and active-task capacity before work is queued.

Fingerprint and IP reservations are separate document updates. The server reserves both using the task token: if either conditional update fails, it compensates the successful update before rejecting the task. A crash can therefore only leave an overly strict stale reservation, never an uncounted task; the reconciliation job removes stale task-scoped reservations. This preserves fail-closed quota behavior without requiring cross-document transactions.

### `access_rules`

Stores whitelist and blacklist rules, rule type, normalized value or HMAC identifier, operator note, creator, and timestamps. Raw IP addresses exist only when an operator explicitly creates an IP rule. Public task and usage documents never store raw IP addresses.

### Django-owned collections

The official MongoDB backend stores Django staff users, permissions, sessions, and admin records. Fetchly does not create a parallel administrator identity system.

## 8. Visitor identity and privacy

The browser generates a stable, versioned fingerprint from a deliberately small set of browser characteristics. The server combines it with the normalized client IP.

Three HMAC identifiers are calculated with a rotating application secret:

- fingerprint identifier;
- IP identifier;
- owner identifier from fingerprint plus IP.

Quota enforcement uses the greater usage of the separate fingerprint and IP identifiers. History and task authorization require the combined owner identifier. Operator views mask IP-derived information by default. Secret rotation must support the current and previous key during a bounded transition period.

Trusted proxy headers are accepted only from explicitly configured reverse-proxy addresses.

## 9. Public user experience

The homepage is a single mobile-first flow:

1. Paste or type a URL.
2. Inspect the URL and show platform, thumbnail, title, duration, and available choices.
3. Present friendly presets such as best video, data saver, and audio only. Technical format details remain in a progressive-disclosure panel.
4. Submit the selected server-owned format snapshot.
5. Show queued/downloading progress through HTMX polling.
6. Reveal a download button and explicit expiry time when the file is ready.

Recent history appears below the main flow for the current fingerprint-and-IP owner. Entries show status, size, creation time, expiry, and a download action while available.

The visual system is playful and welcoming rather than technical: bright controlled color, rounded shapes, source/status iconography, concise Indonesian copy, subtle motion, and device-driven dark mode. Accessibility requirements include keyboard operation, visible focus, reduced-motion support, semantic status announcements, sufficient contrast, stable layouts, and touch targets of at least 44 CSS pixels.

## 10. Admin experience

Staff authenticate through Django authentication with secure cookie settings and an expiring session. The custom dashboard shows:

- total, queued, active, completed, failed, and expired tasks;
- success rate and processing duration by provider;
- Redis queue depth and oldest queued task;
- temporary storage usage and cleanup health;
- quota usage and active visitor counts;
- searchable task history with masked visitor identifiers;
- whitelist and blacklist management with audit metadata.

Destructive actions require POST requests, CSRF validation, and confirmation. Internal resolver cookies and secrets are never rendered in the dashboard.

## 11. Request and job flow

### Inspection

1. Django validates JSON/form shape, URL syntax, allowed schemes, CAPTCHA, visitor rate limit, and blacklist rules.
2. URL validation resolves DNS safely and rejects local, private, link-local, loopback, multicast, and otherwise nonpublic destinations. Every redirect and provider-resolved URL is revalidated.
3. Django creates an `inspection_queued` task owned by the current visitor and queues inspection. The worker changes it to `inspecting` only after claiming it.
4. The worker selects a provider, obtains formats, normalizes them to the shared provider contract, and saves a short-lived server-side snapshot.
5. HTMX polling replaces the result fragment with format cards or an actionable error.

### Download

1. The browser submits only the public task token and selected format ID.
2. Django verifies owner, inspection expiry, format membership, rate limit, quota, and active-job capacity.
3. Compensating atomic usage updates reserve estimated bytes when known and an active-task slot against both fingerprint and IP identifiers. Unknown sizes receive a conservative reservation and strict streaming/process size enforcement.
4. Django sets `download_queued`; the worker changes it to `downloading` only after claiming the job, then downloads and converts into a task-specific temporary path. Paths and filenames are generated only by the server.
5. Completion atomically converts the reservation into actual charged usage. Failure releases unused reservation but charges bytes actually transferred when policy requires it.
6. The owner receives the file through an authorized Django response. Completed files remain available only until their configured expiry.

The browser never submits or receives resolver cookies, captured referers, arbitrary output paths, or authoritative resolved media URLs.

## 12. Failure handling

User-facing errors use stable codes and Indonesian messages for invalid URLs, unsupported/private content, CAPTCHA failure, quota exhaustion, rate limiting, provider blocking, unavailable formats, oversized files, timeout, expired files, and temporary provider failures.

Internal diagnostics retain provider name, operation, exception class, safe stderr tail, request ID, and task ID. Raw cookies, authorization headers, full signed media URLs, fingerprints, and unmasked IPs are redacted.

Only explicitly classified transient network and provider errors retry, with exponential backoff and at most two retries. Validation, authorization, quota, unsupported-media, and size failures never retry. RQ job timeouts exceed the provider subprocess timeout slightly so cleanup can run before the worker is terminated.

Workers handle shutdown signals by stopping new work and returning interrupted jobs to a recoverable state. A reconciliation job detects stale states and either requeues safe work or marks it failed with a recoverable error.

## 13. Cleanup and retention

A scheduled RQ job:

- deletes expired completed files;
- removes partial files from failed or interrupted jobs;
- expires inspection snapshots and resolver context;
- marks missing completed files as expired;
- reconciles stale jobs;
- deletes old task documents according to the configured history-retention period.

Downloaded files are not backed up. MongoDB backup policy covers staff accounts, access rules, quota state, and retained operational history.

## 14. Security controls

- SSRF-safe validation at input, redirect, iframe, manifest, and resolved-media boundaries.
- Server-owned format and resolver state.
- Django CSRF protection and secure session cookies.
- CAPTCHA and separate rate limits for inspection, download submission, status access, file access, and admin login.
- Atomic quota reservation and per-identity active-job limits.
- HMAC-derived ownership identifiers and constant-time verification for signed sensitive tokens.
- Random nonsequential public task tokens distinct from MongoDB IDs.
- Task-specific directories, sanitized download names, fixed command argument construction, and no shell execution.
- Hard process timeouts, media-size monitoring, partial-file cleanup, and container resource limits.
- Encrypted resolver context with short expiry and log redaction.
- Dependency pinning and repeatable container builds.

## 15. Observability and health

Structured JSON logs contain request ID, task ID, provider, state, elapsed time, and safe error code. Metrics cover request rate, queue wait, processing duration, success/failure by provider, retries, quota rejection, rate limiting, worker availability, and temporary storage.

Health endpoints distinguish:

- liveness: the web process responds;
- readiness: MongoDB and Redis are reachable and the downloads volume is writable;
- worker health: recent heartbeat and queue age;
- capability health: FFmpeg, `yt-dlp`, and Playwright browser availability.

Detailed health data is staff-only; the public endpoint returns only overall readiness.

## 16. Testing strategy

- Unit tests: URL and redirect validation, provider routing, normalized format contracts, HMAC identity, quota reservation, state transitions, and error mapping.
- MongoDB/Redis integration tests: indexes, atomic quota updates, ownership queries, queue submission, retry behavior, and reconciliation.
- Worker tests: fake subprocesses for success, timeout, restart, oversized output, partial cleanup, and safe command construction.
- Provider contract tests: sanitized fixtures ensure every provider returns the same domain result shape.
- Browser tests: paste-to-download flow, format selection, history, expired files, CAPTCHA, mobile layout, dark mode, reduced motion, keyboard use, and admin actions.
- Docker smoke tests: migrations, static collection, readiness, worker heartbeat, and a synthetic local media job.

Routine tests do not call external media sites. Explicit live provider smoke tests run separately because provider behavior is unstable and may be rate limited.

## 17. Delivery boundaries

The rebuild replaces the current application in staged, testable slices within the same repository. The implementation plan must preserve a runnable checkpoint after infrastructure/model setup, provider extraction, public flow, worker flow, and admin flow. Final cutover occurs only after Docker smoke tests and the critical browser journey pass.

The old Flask code can be removed only after feature parity has been verified. No old SQLite data is imported.

## 18. Acceptance criteria

- A visitor can inspect and download supported public media from a responsive Indonesian interface without an account.
- History and quota enforcement are based on fingerprint plus IP and cannot be bypassed through parallel submissions within the defined limits.
- Web restart does not discard queued jobs; interrupted jobs reconcile predictably.
- Sensitive resolver data never travels through the browser or appears in logs/admin pages.
- Files expire and are removed automatically.
- Staff can monitor jobs and manage whitelist/blacklist rules through authenticated pages.
- The system starts through Docker Compose without WARP and reports actionable health status.
- Automated tests cover the critical state, security, quota, worker, and browser flows.
