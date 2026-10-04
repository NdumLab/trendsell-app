# TrendSell frontend

React 19 + TypeScript on Vite. See the [root README](../README.md) for the product and the evidence
rules the interface has to honour.

```bash
npm ci
npm run dev        # http://localhost:3000, proxies /api to http://127.0.0.1:8001
npm test           # vitest: decision contract, identifier contract, sensitivity
npm run typecheck  # tsc --noEmit
npm run build      # typecheck, then a production bundle in dist/
```

## Layout

```
src/features/   Today · Xray · Products (discover, product, market gaps) · DecisionRoom · Operations
src/shared/     Workspace (auth, demo, workspace records) · UI (badges, modal, evidence drawer, cards)
src/lib/        api · economics · identifier · csv · utils
src/index.css   design tokens, components and responsive rules — no CSS framework
src/demo.ts     opt-in demo fixtures, loaded lazily and labelled Demo everywhere they appear
```

## Rules this codebase keeps

- A number on screen carries a `TruthBadge`, or it is not shown.
- `Unavailable` renders as a reason, never as an empty card or a zero.
- Nothing in `demo.ts` is reachable outside an explicitly entered demo workspace, and it uses its own
  local-storage namespace.
- `lib/economics.ts` mirrors `backend/app/economics.py`. Both are held to
  `contracts/economics_cases.json`, so a change to one without the other fails CI.
- `lib/identifier.ts` mirrors `backend/app/security.py:resolve_input`, held to
  `contracts/identifier_cases.json`. It parses identifiers only — the app never fetches a
  user-supplied URL.
