# UX Contract

## Product context

- Audience: pengguna umum Indonesia dan staf operator.
- Primary jobs: inspeksi tautan, pilih format, unduh file sementara; staf memantau operasi.
- Target market(s): Indonesia.
- Active locales: `id-ID`.
- Language/content register: ramah, lugas, tanpa jargon internal.
- Timezone/calendar policy: `Asia/Jakarta`, kalender Gregorian.
- Accessibility target: WCAG 2.2 AA.

## Business-context sources

| Domain / scope | Authoritative source | Source type | Reviewed date |
|---|---|---|---|
| Task lifecycle and ownership | `docs/superpowers/specs/2026-08-31-fetchly-total-rebuild-design.md` | Product/security spec | 2026-08-31 |
| Implementation interfaces | `docs/superpowers/plans/2026-08-31-fetchly-total-rebuild.md` | Delivery plan | 2026-08-31 |

## Visual contract

- Project `DESIGN.md`: `DESIGN.md`.
- Token ownership model: DESIGN.md generated/manual source.
- Runtime token source: `static/css/app.css`.
- Mapping: frontmatter semantic role → same-named CSS custom property → shared class.
- Token drift gate: DESIGN lint, premium audit, browser screenshot comparison.
- Supported themes: light, dark, system default.

## Canonical UI Map

| Capability | Canonical owner | Source of truth | Allowed variants | Verification |
|---|---|---|---|---|
| Form | Django form markup + shared field CSS | This contract | inspect / download | request + browser tests |
| Select/Listbox | native `<select>` controls | This contract | status / access rule | keyboard + browser tests |
| Scrollbar | `static/css/app.css` global rules | DESIGN.md | stable-gutter regions | computed style |
| Toast | shared `aria-live` status region | This contract | success / warning / info / error | browser live-region test |
| CRUD | Django service/state machine | domain tests | public task / staff rule | full-flow E2E |

## Component behavior

| Component | Default | Hover | Focus | Active | Disabled | Busy | Error |
|---|---|---|---|---|---|---|---|
| Button | clear intent | tone shift | 3px ring | press 1px | dim + blocked | fixed size + status | inline recovery |
| Icon button | accessible name | surface shift | 3px ring | press 1px | dim | fixed slot | nearby status |
| Input | label + help slot | stronger border | ring + border | n/a | muted | readonly only if needed | text + aria-invalid |
| Table/list | stable rows | surface shift | link/action ring | selected outline | n/a | stable placeholder | retry row |

## Dataset navigation

- Admin tables: server pagination; state in query string.
- Exploratory lists: 20 most recent owner tasks, newest first.
- Empty/no-results/error/loading: distinct copy and recovery; stable footprint.
- Selection scope: no bulk selection until a real staff workflow requires it.

## Flow ledger

| Operation | Trigger | Pending | Success destination | Success feedback | Failure recovery | Focus outcome | Source ref |
|---|---|---|---|---|---|---|---|
| Inspect URL | Cari format | button busy + polite status | same page formats | media ticket | inline correction / retry | result heading | task spec |
| Prepare download | Siapkan unduhan | progress status | same page completed | Unduh sekarang | safe error + retry | status heading | task spec |
| Download file | Unduh sekarang | browser transfer | same page | history updates | expiry explanation | trigger remains | task spec |
| Access-rule mutation | staff form | button busy | dashboard list | shared status | form preserved | changed row/field | task spec |

## Navigation and responsive behavior

- Document titles name Fetchly and current staff screen.
- Unauthorized or missing routes use safe Django responses without exposing internals; task errors explain the next action inline.
- Desktop history rail becomes a normal downstream section below 56rem.
- File/task URLs reveal no internal ID; wrong-owner and missing both return 404.
- Focus is never hidden by sticky UI.

## Overlays and feedback

- Dialog primitive: styled native `<dialog>` only where confirmation is required.
- Alerts remain inline when the user must correct something.
- Status uses a single polite live region with stable placement and deduped copy.
- Layer order: dialog backdrop → dialog → status/toast → tooltip.

## Async and resilience

- Mutations are pessimistic; jobs are queued and idempotently claimed.
- Duplicate submit is disabled while the active request is pending.
- Polling stops on ready, completed, failed, blocked, or expired.
- Transient worker failures retry twice with exponential delay.
- Reload restores authorized history via fingerprint+IP owner identity.

## Validation

- Django/service validation is authoritative; HTML hints improve keyboards only.
- Validate on submit, then clear a field error after correction.
- Use `novalidate`, focus first invalid field, preserve URL on recoverable error.
- Never render raw provider errors or sensitive resolver data.

## Permission and clipboard

- Unauthorized task/file access returns the same 404 as a missing task.
- Clipboard paste is user-triggered and has a normal manual-input fallback.
- No secret is copied or shown in status text.

## Verification

- Static: Ruff, Django check, premium strict audit, DESIGN lint.
- Browser: Chromium desktop 1440px, mobile 390px, light/dark/reduced-motion/keyboard.
- Accessibility: semantic forms, focus-visible, live regions, contrast, zoom/overflow.
- Visual regression: compare against both files in `docs/design/concepts/`.
