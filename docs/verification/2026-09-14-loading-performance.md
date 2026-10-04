# Workspace loading measurement — 2026-09-14

This is a controlled local browser measurement, not a production latency claim. It was
run by `frontend/e2e/loading-performance.spec.ts` against the disposable Playwright
FastAPI/Vite stack on the same host, using Chromium and a fresh test workspace.

| Journey | Time to visible usable content |
| --- | ---: |
| Fresh signed-out visit | 1,048.7 ms |
| Fresh authenticated visit | 900.9 ms |
| Client-side Today → Product X-Ray navigation | 185.0 ms |

The authenticated request trace showed `/auth/me` completing before the four workspace
list requests began. Products, decisions, quotes, and watchlist requests then started
within a 1.6 ms span, confirming a one-step authentication bootstrap followed by a
parallel fan-out rather than a serial list waterfall.

The earlier review's 12-second figure was an artificial wait, not a measured duration,
and is not treated as a confirmed defect. Production time-to-content remains unmeasured
from this coding shell because its outbound web access is isolated. The browser test
keeps a generous five-second regression ceiling to detect a fixed delay or unresolved
loading state without pretending local timing is a production service-level objective.
