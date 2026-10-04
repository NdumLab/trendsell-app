# Dependency license disposition

This inventory is generated from the exact Python and npm lockfiles by
`scripts/check_dependency_licenses.py`. CI fails when an installed version differs from a
lock, the report is stale, a license is missing, or a dependency falls outside the policy.
It is an engineering compatibility decision for this release, not jurisdiction-specific
legal advice.

## Decision

**PASS — 181 direct and transitive packages have an approved disposition.**

- Permissive licenses approved: 0BSD, Apache-2.0, BSD-2-Clause, BSD-3-Clause, ISC,
  MIT and PSF-2.0.
- LGPL-3.0-only is approved only for the unmodified `psycopg` server driver packages.
  They are separately installed from the lock, are not linked into the browser, and must
  retain upstream notices plus users' replacement/modification rights.
- MPL-2.0 is approved only for the `lightningcss` build tool and its optional platform
  packages. Those packages are not shipped in the release artifact; their generated CSS is.
- A new, missing, strong-copyleft, source-available or otherwise unapproved license blocks CI
  until an accountable reviewer records a new disposition.
- Copyright, license and NOTICE material supplied by dependencies must remain intact wherever
  dependency code is redistributed. This inventory must ship with the release artifact.

## Locked inputs

| Lockfile | SHA-256 |
| --- | --- |
| `backend/requirements.lock` | `2d8e8b6eeed0774a0231e0850915b742d6b4e84f4233fb860704723db89e17ac` |
| `backend/requirements-dev.lock` | `6f4abd3e64431d96878397c0c8501675c0d096da3bfe00d2ac12d1e91eb9884b` |
| `frontend/package-lock.json` | `d14afcf1daf7f11ef417d0fc6e8ee903889d6ce5f501036749b0d10c08854c2e` |

## Inventory summary

| Ecosystem | Scope | Packages |
| --- | --- | ---: |
| Python | development | 10 |
| Python | runtime | 21 |
| npm | development | 69 |
| npm | runtime | 81 |

## Exact inventory

| Ecosystem | Scope | Package | Version | License | Disposition |
| --- | --- | --- | --- | --- | --- |
| Python | development | `Pygments` | `2.21.0` | BSD-2-Clause | Approved permissive |
| Python | development | `execnet` | `2.1.2` | MIT | Approved permissive |
| Python | development | `httpcore2` | `2.12.0` | BSD-3-Clause | Approved permissive |
| Python | development | `httpx2` | `2.12.0` | BSD-3-Clause | Approved permissive |
| Python | development | `iniconfig` | `2.3.0` | MIT | Approved permissive |
| Python | development | `packaging` | `26.3` | Apache-2.0 OR BSD-2-Clause | Approved permissive |
| Python | development | `pluggy` | `1.6.0` | MIT | Approved permissive |
| Python | development | `pytest` | `9.0.3` | MIT | Approved permissive |
| Python | development | `pytest-xdist` | `3.8.0` | MIT | Approved permissive |
| Python | development | `truststore` | `0.10.4` | MIT | Approved permissive |
| Python | runtime | `Mako` | `1.4.1` | MIT | Approved permissive |
| Python | runtime | `MarkupSafe` | `3.0.3` | BSD-3-Clause | Approved permissive |
| Python | runtime | `SQLAlchemy` | `2.0.48` | MIT | Approved permissive |
| Python | runtime | `alembic` | `1.18.4` | MIT | Approved permissive |
| Python | runtime | `annotated-doc` | `0.0.5` | MIT | Approved permissive |
| Python | runtime | `annotated-types` | `0.8.0` | MIT | Approved permissive |
| Python | runtime | `anyio` | `4.15.1` | MIT | Approved permissive |
| Python | runtime | `click` | `8.5.0` | BSD-3-Clause | Approved permissive |
| Python | runtime | `fastapi` | `0.135.1` | MIT | Approved permissive |
| Python | runtime | `greenlet` | `3.5.5` | MIT AND PSF-2.0 | Approved permissive |
| Python | runtime | `h11` | `0.16.0` | MIT | Approved permissive |
| Python | runtime | `idna` | `3.19` | BSD-3-Clause | Approved permissive |
| Python | runtime | `psycopg` | `3.3.3` | LGPL-3.0-only | Approved server exception |
| Python | runtime | `psycopg-binary` | `3.3.3` | LGPL-3.0-only | Approved server exception |
| Python | runtime | `pydantic` | `2.12.5` | MIT | Approved permissive |
| Python | runtime | `pydantic_core` | `2.41.5` | MIT | Approved permissive |
| Python | runtime | `python-dotenv` | `1.2.2` | BSD-3-Clause | Approved permissive |
| Python | runtime | `starlette` | `1.6.0` | BSD-3-Clause | Approved permissive |
| Python | runtime | `typing-inspection` | `0.4.4` | MIT | Approved permissive |
| Python | runtime | `typing_extensions` | `4.16.0` | PSF-2.0 | Approved permissive |
| Python | runtime | `uvicorn` | `0.41.0` | BSD-3-Clause | Approved permissive |
| npm | development | `@jridgewell/resolve-uri` | `3.1.2` | MIT | Approved permissive |
| npm | development | `@jridgewell/sourcemap-codec` | `1.6.0` | MIT | Approved permissive |
| npm | development | `@jridgewell/trace-mapping` | `0.3.31` | MIT | Approved permissive |
| npm | development | `@oxc-project/types` | `0.148.0` | MIT | Approved permissive |
| npm | development | `@playwright/test` | `1.63.0` | Apache-2.0 | Approved permissive |
| npm | development | `@rolldown/binding-android-arm-eabi` | `1.2.7` | MIT | Approved permissive |
| npm | development | `@rolldown/binding-android-arm64` | `1.2.7` | MIT | Approved permissive |
| npm | development | `@rolldown/binding-darwin-arm64` | `1.2.7` | MIT | Approved permissive |
| npm | development | `@rolldown/binding-darwin-x64` | `1.2.7` | MIT | Approved permissive |
| npm | development | `@rolldown/binding-freebsd-x64` | `1.2.7` | MIT | Approved permissive |
| npm | development | `@rolldown/binding-linux-arm-gnueabihf` | `1.2.7` | MIT | Approved permissive |
| npm | development | `@rolldown/binding-linux-arm64-gnu` | `1.2.7` | MIT | Approved permissive |
| npm | development | `@rolldown/binding-linux-arm64-musl` | `1.2.7` | MIT | Approved permissive |
| npm | development | `@rolldown/binding-linux-ppc64-gnu` | `1.2.7` | MIT | Approved permissive |
| npm | development | `@rolldown/binding-linux-s390x-gnu` | `1.2.7` | MIT | Approved permissive |
| npm | development | `@rolldown/binding-linux-x64-gnu` | `1.2.7` | MIT | Approved permissive |
| npm | development | `@rolldown/binding-linux-x64-musl` | `1.2.7` | MIT | Approved permissive |
| npm | development | `@rolldown/binding-openharmony-arm64` | `1.2.7` | MIT | Approved permissive |
| npm | development | `@rolldown/binding-win32-arm64-msvc` | `1.2.7` | MIT | Approved permissive |
| npm | development | `@rolldown/binding-win32-x64-msvc` | `1.2.7` | MIT | Approved permissive |
| npm | development | `@rolldown/pluginutils` | `1.0.1` | MIT | Approved permissive |
| npm | development | `@types/chai` | `5.2.3` | MIT | Approved permissive |
| npm | development | `@types/deep-eql` | `4.0.2` | MIT | Approved permissive |
| npm | development | `@types/estree` | `1.0.9` | MIT | Approved permissive |
| npm | development | `@types/node` | `22.19.15` | MIT | Approved permissive |
| npm | development | `@vitejs/plugin-react` | `6.1.1` | MIT | Approved permissive |
| npm | development | `@vitest/mocker` | `5.0.0` | MIT | Approved permissive |
| npm | development | `@vitest/spy` | `5.0.0` | MIT | Approved permissive |
| npm | development | `assertion-error` | `2.0.1` | MIT | Approved permissive |
| npm | development | `chai` | `6.2.2` | MIT | Approved permissive |
| npm | development | `detect-libc` | `2.1.2` | Apache-2.0 | Approved permissive |
| npm | development | `es-module-lexer` | `2.3.2` | MIT | Approved permissive |
| npm | development | `estree-walker` | `3.0.3` | MIT | Approved permissive |
| npm | development | `expect-type` | `1.4.0` | Apache-2.0 | Approved permissive |
| npm | development | `fdir` | `6.5.0` | MIT | Approved permissive |
| npm | development | `fsevents` | `2.3.3` | MIT | Approved permissive |
| npm | development | `lightningcss` | `1.33.0` | MPL-2.0 | Approved build-only exception |
| npm | development | `lightningcss-android-arm64` | `1.33.0` | MPL-2.0 | Approved build-only exception |
| npm | development | `lightningcss-darwin-arm64` | `1.33.0` | MPL-2.0 | Approved build-only exception |
| npm | development | `lightningcss-darwin-x64` | `1.33.0` | MPL-2.0 | Approved build-only exception |
| npm | development | `lightningcss-freebsd-x64` | `1.33.0` | MPL-2.0 | Approved build-only exception |
| npm | development | `lightningcss-linux-arm-gnueabihf` | `1.33.0` | MPL-2.0 | Approved build-only exception |
| npm | development | `lightningcss-linux-arm64-gnu` | `1.33.0` | MPL-2.0 | Approved build-only exception |
| npm | development | `lightningcss-linux-arm64-musl` | `1.33.0` | MPL-2.0 | Approved build-only exception |
| npm | development | `lightningcss-linux-x64-gnu` | `1.33.0` | MPL-2.0 | Approved build-only exception |
| npm | development | `lightningcss-linux-x64-musl` | `1.33.0` | MPL-2.0 | Approved build-only exception |
| npm | development | `lightningcss-win32-arm64-msvc` | `1.33.0` | MPL-2.0 | Approved build-only exception |
| npm | development | `lightningcss-win32-x64-msvc` | `1.33.0` | MPL-2.0 | Approved build-only exception |
| npm | development | `magic-string` | `1.2.3` | MIT | Approved permissive |
| npm | development | `nanoid` | `3.3.18` | MIT | Approved permissive |
| npm | development | `obug` | `2.1.4` | MIT | Approved permissive |
| npm | development | `picocolors` | `1.1.1` | ISC | Approved permissive |
| npm | development | `picomatch` | `4.0.7` | MIT | Approved permissive |
| npm | development | `playwright` | `1.63.0` | Apache-2.0 | Approved permissive |
| npm | development | `playwright-core` | `1.63.0` | Apache-2.0 | Approved permissive |
| npm | development | `postcss` | `8.5.28` | MIT | Approved permissive |
| npm | development | `rolldown` | `1.2.7` | MIT | Approved permissive |
| npm | development | `siginfo` | `2.0.0` | ISC | Approved permissive |
| npm | development | `source-map-js` | `1.2.1` | BSD-3-Clause | Approved permissive |
| npm | development | `stackback` | `0.0.2` | MIT | Approved permissive |
| npm | development | `std-env` | `4.2.0` | MIT | Approved permissive |
| npm | development | `tinybench` | `6.1.4` | MIT | Approved permissive |
| npm | development | `tinyexec` | `1.3.0` | MIT | Approved permissive |
| npm | development | `tinyglobby` | `0.2.17` | MIT | Approved permissive |
| npm | development | `typescript` | `5.9.3` | Apache-2.0 | Approved permissive |
| npm | development | `undici-types` | `6.21.0` | MIT | Approved permissive |
| npm | development | `vite` | `8.2.2` | MIT | Approved permissive |
| npm | development | `vitest` | `5.0.0` | MIT | Approved permissive |
| npm | development | `why-is-node-running` | `2.3.0` | MIT | Approved permissive |
| npm | runtime | `@radix-ui/primitive` | `1.1.2` | MIT | Approved permissive |
| npm | runtime | `@radix-ui/react-compose-refs` | `1.1.2` | MIT | Approved permissive |
| npm | runtime | `@radix-ui/react-context` | `1.1.2` | MIT | Approved permissive |
| npm | runtime | `@radix-ui/react-dialog` | `1.1.11` | MIT | Approved permissive |
| npm | runtime | `@radix-ui/react-dismissable-layer` | `1.1.7` | MIT | Approved permissive |
| npm | runtime | `@radix-ui/react-focus-guards` | `1.1.2` | MIT | Approved permissive |
| npm | runtime | `@radix-ui/react-focus-scope` | `1.1.4` | MIT | Approved permissive |
| npm | runtime | `@radix-ui/react-id` | `1.1.1` | MIT | Approved permissive |
| npm | runtime | `@radix-ui/react-portal` | `1.1.6` | MIT | Approved permissive |
| npm | runtime | `@radix-ui/react-presence` | `1.1.4` | MIT | Approved permissive |
| npm | runtime | `@radix-ui/react-primitive` | `2.1.0` | MIT | Approved permissive |
| npm | runtime | `@radix-ui/react-slot` | `1.2.0` | MIT | Approved permissive |
| npm | runtime | `@radix-ui/react-use-callback-ref` | `1.1.1` | MIT | Approved permissive |
| npm | runtime | `@radix-ui/react-use-controllable-state` | `1.2.2` | MIT | Approved permissive |
| npm | runtime | `@radix-ui/react-use-effect-event` | `0.0.2` | MIT | Approved permissive |
| npm | runtime | `@radix-ui/react-use-escape-keydown` | `1.1.1` | MIT | Approved permissive |
| npm | runtime | `@radix-ui/react-use-layout-effect` | `1.1.1` | MIT | Approved permissive |
| npm | runtime | `@reduxjs/toolkit` | `2.12.0` | MIT | Approved permissive |
| npm | runtime | `@standard-schema/spec` | `1.1.0` | MIT | Approved permissive |
| npm | runtime | `@standard-schema/utils` | `0.3.0` | MIT | Approved permissive |
| npm | runtime | `@tanstack/query-core` | `5.56.2` | MIT | Approved permissive |
| npm | runtime | `@tanstack/react-query` | `5.56.2` | MIT | Approved permissive |
| npm | runtime | `@types/d3-array` | `3.2.2` | MIT | Approved permissive |
| npm | runtime | `@types/d3-color` | `3.1.3` | MIT | Approved permissive |
| npm | runtime | `@types/d3-ease` | `3.0.2` | MIT | Approved permissive |
| npm | runtime | `@types/d3-interpolate` | `3.0.4` | MIT | Approved permissive |
| npm | runtime | `@types/d3-path` | `3.1.1` | MIT | Approved permissive |
| npm | runtime | `@types/d3-scale` | `4.0.9` | MIT | Approved permissive |
| npm | runtime | `@types/d3-shape` | `3.2.0` | MIT | Approved permissive |
| npm | runtime | `@types/d3-time` | `3.0.4` | MIT | Approved permissive |
| npm | runtime | `@types/d3-timer` | `3.0.2` | MIT | Approved permissive |
| npm | runtime | `@types/react` | `19.2.14` | MIT | Approved permissive |
| npm | runtime | `@types/react-dom` | `19.2.3` | MIT | Approved permissive |
| npm | runtime | `@types/use-sync-external-store` | `0.0.6` | MIT | Approved permissive |
| npm | runtime | `aria-hidden` | `1.2.6` | MIT | Approved permissive |
| npm | runtime | `clsx` | `2.1.1` | MIT | Approved permissive |
| npm | runtime | `cookie` | `1.1.1` | MIT | Approved permissive |
| npm | runtime | `csstype` | `3.2.3` | MIT | Approved permissive |
| npm | runtime | `d3-array` | `3.2.4` | ISC | Approved permissive |
| npm | runtime | `d3-color` | `3.1.0` | ISC | Approved permissive |
| npm | runtime | `d3-ease` | `3.0.1` | BSD-3-Clause | Approved permissive |
| npm | runtime | `d3-format` | `3.1.2` | ISC | Approved permissive |
| npm | runtime | `d3-interpolate` | `3.0.1` | ISC | Approved permissive |
| npm | runtime | `d3-path` | `3.1.0` | ISC | Approved permissive |
| npm | runtime | `d3-scale` | `4.0.2` | ISC | Approved permissive |
| npm | runtime | `d3-shape` | `3.2.0` | ISC | Approved permissive |
| npm | runtime | `d3-time` | `3.1.0` | ISC | Approved permissive |
| npm | runtime | `d3-time-format` | `4.1.0` | ISC | Approved permissive |
| npm | runtime | `d3-timer` | `3.0.1` | ISC | Approved permissive |
| npm | runtime | `decimal.js-light` | `2.5.1` | MIT | Approved permissive |
| npm | runtime | `detect-node-es` | `1.1.0` | MIT | Approved permissive |
| npm | runtime | `es-toolkit` | `1.52.0` | MIT | Approved permissive |
| npm | runtime | `eventemitter3` | `5.0.4` | MIT | Approved permissive |
| npm | runtime | `get-nonce` | `1.0.1` | MIT | Approved permissive |
| npm | runtime | `immer` | `10.2.0` | MIT | Approved permissive |
| npm | runtime | `immer` | `11.1.18` | MIT | Approved permissive |
| npm | runtime | `internmap` | `2.0.3` | ISC | Approved permissive |
| npm | runtime | `lucide-react` | `0.516.0` | ISC | Approved permissive |
| npm | runtime | `react` | `19.0.0` | MIT | Approved permissive |
| npm | runtime | `react-dom` | `19.0.0` | MIT | Approved permissive |
| npm | runtime | `react-is` | `19.2.8` | MIT | Approved permissive |
| npm | runtime | `react-redux` | `9.3.0` | MIT | Approved permissive |
| npm | runtime | `react-remove-scroll` | `2.7.2` | MIT | Approved permissive |
| npm | runtime | `react-remove-scroll-bar` | `2.3.8` | MIT | Approved permissive |
| npm | runtime | `react-router` | `7.18.3` | MIT | Approved permissive |
| npm | runtime | `react-router-dom` | `7.18.3` | MIT | Approved permissive |
| npm | runtime | `react-style-singleton` | `2.2.3` | MIT | Approved permissive |
| npm | runtime | `recharts` | `3.6.0` | MIT | Approved permissive |
| npm | runtime | `redux` | `5.0.1` | MIT | Approved permissive |
| npm | runtime | `redux-thunk` | `3.1.0` | MIT | Approved permissive |
| npm | runtime | `reselect` | `5.1.1` | MIT | Approved permissive |
| npm | runtime | `scheduler` | `0.25.0` | MIT | Approved permissive |
| npm | runtime | `set-cookie-parser` | `2.7.2` | MIT | Approved permissive |
| npm | runtime | `sonner` | `2.0.3` | MIT | Approved permissive |
| npm | runtime | `tailwind-merge` | `3.2.0` | MIT | Approved permissive |
| npm | runtime | `tiny-invariant` | `1.3.3` | MIT | Approved permissive |
| npm | runtime | `tslib` | `2.8.1` | 0BSD | Approved permissive |
| npm | runtime | `use-callback-ref` | `1.3.3` | MIT | Approved permissive |
| npm | runtime | `use-sidecar` | `1.1.3` | MIT | Approved permissive |
| npm | runtime | `use-sync-external-store` | `1.6.0` | MIT | Approved permissive |
| npm | runtime | `victory-vendor` | `37.3.6` | MIT AND ISC | Approved permissive |
