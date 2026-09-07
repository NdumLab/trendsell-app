# Archived synthetic prototype

These files preserve the original UI, fixture generators, connectors, and tests
from commit `66c75e4`. They are outside the active frontend build and backend
import path. Do not deploy or import this package. Its market numbers are
synthetic and its old tests assert behavior deliberately retired by the redesign.

The active application is `frontend/src` and `backend/app`. Explicit browser
demo examples live in `frontend/src/demo.ts`, carry Demo labels, and use their
own local-storage namespace. Production APIs never load them.
