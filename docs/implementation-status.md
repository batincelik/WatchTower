# Implementation status

This file records implemented behavior without treating scaffolding as completion.

| Phase | Status | Evidence / remaining work |
|---|---|---|
| 1 Foundation | Partial | Monorepo, API, dashboard, PostgreSQL, Redis, Compose, scheduler and Playwright worker image exist. Docker image build is pending validation after local Docker storage is freed. |
| 2 Authentication | Missing | Admin setup, Argon2id login, secure sessions and CSRF are not implemented. |
| 3 Monitor domain | Partial | Create/list/detail, pause/resume, check history and queued Check Now exist. Update/delete and ownership isolation remain. |
| 4 Security | Partial | URL scheme/credential checks, DNS answer validation, default-denied non-public IPv4/IPv6, redirect revalidation, DNS-pinned HTTP connections, size bounds and regression tests exist. Browser routing and webhook enforcement remain. |
| 5 Scheduler | Partial | Centralized scheduler uses `FOR UPDATE SKIP LOCKED`, transactional `next_check_at`, and active-job suppression. Durable queue outbox/reconciliation remains. |
| 6 HTTP monitoring | Implemented core | Bounded streaming HTTP fetch, status/text/HTML/element extraction and stable errors exist. Per-domain rate limiting remains. |
| 7 Browser monitoring | Missing | Worker image exists; browser pool, isolated contexts and navigation interception do not. |
| 8 Snapshots | Partial | Normalized candidates, SHA-256 and transactional snapshot persistence exist. Filesystem storage abstraction is not yet implemented. |
| 9 Text / HTML diff | Partial | Real unified diffs, baseline establishment and thresholds exist. More normalization controls and bounded regex execution remain. |
| 10 Visual monitoring | Missing | Screenshot capture, storage and pixel diff are not implemented. |
| 11 Price / availability | Partial | International price parsing and basic text rules exist. Configurable availability API rules and complete transition semantics remain. |
| 12 Notifications | Missing | Durable outbox, encrypted channel secrets and delivery workers remain. |
| 13 Dashboard | Partial | Production page reads the real monitor API and contains no fixture data. Authentication, details, changes and controls remain. |
| 14 Preview UX | Missing | Background preview jobs remain. |
| 15 Reliability | Partial | Check leases and idempotent snapshot/change constraints exist. Heartbeats and stale recovery remain. |
| 16 Retention | Missing | Incremental retention and orphan cleanup remain. |
| 17 Tests | Partial | 29 unit/security tests pass. PostgreSQL/Redis/browser/failure integration and E2E suites remain. |
| 18 Documentation | Partial | README and this audit exist; the required documentation set remains. |
| 19 GitHub polish | Partial | Deterministic mutable demo site exists. CI and contributor assets remain. |

The earliest incomplete phase is Phase 1 until a clean Docker build is verified, followed by Phase 2.
