# Third-Party Notices

Stand: 20.10.2026. This inventory was prepared from the committed lockfiles
backend/requirements.lock, uv.lock, and frontend/package-lock.json, and
cross-checked against the metadata of the installed Python and Node packages.
It is an engineering inventory, not legal advice or a legal opinion.

## License scope

The original SoulFlow program source released with these notices is licensed
under **GNU Affero General Public License v3.0 only (AGPL-3.0-only)**, unless
a file or component says otherwise. The unmodified complete license text is in
LICENSE. The AGPL does not replace or relicense third-party components, data,
quoted source titles, or external websites. Those keep the licenses and rights
listed below. Product names and marks remain subject to applicable trademark
rights independently of the source-code license.

For a network deployment, the source link should identify the exact deployed
revision and expose the corresponding source, build/install instructions,
lockfiles, and local modifications for that revision.

## Embedded engines and data

- **PySwissEph 2.10.3.2 / Swiss Ephemeris** — distributed under GNU AGPL v3
  in this open release. PySwissEph is the Python interface and contains the
  Swiss Ephemeris calculation engine. Upstream: https://pypi.org/project/pyswisseph/
  and https://www.astro.com/swisseph/. No professional-license grant is claimed.
- **timezonefinder 8.3.0** — MIT. Its separately packaged boundary database
  **timezonefinder-data 1.2026.3** is Open Data Commons ODbL 1.0 and is not
  relicensed under the AGPL. Upstream: https://github.com/jannikmi/timezonefinder
  and https://opendatacommons.org/licenses/odbl/1-0/.
- **Local city coordinates in backend/app/astro.py** — five factual coordinate
  snapshots from the identified Wikidata items, marked CC0 in the source.
  Upstream: https://www.wikidata.org/wiki/Wikidata:Licensing and
  https://creativecommons.org/publicdomain/zero/1.0/.
- **Nominatim / OpenStreetMap results** — obtained only when a user explicitly
  searches for a place. Returned records are attributed in the application as
  © OpenStreetMap contributors under ODbL. They are external runtime data, not
  SoulFlow-authored data. See https://www.openstreetmap.org/copyright.
- **IANA time-zone data** — used through Python zoneinfo or the conditional
  tzdata package. The IANA database and the Python package retain their own
  notices; see https://www.iana.org/time-zones and
  https://pypi.org/project/tzdata/.

## Editorial references

The learning modules contain original SoulFlow summaries, exercises, and
questions together with citations to public source pages. The cited websites,
teachers, organisations, course descriptions, and publication titles are not
copied into this repository and are not relicensed under the AGPL. A citation
is not an endorsement or a grant of rights in the referenced work. Source roles
and URLs are recorded in the lesson data and source comments.

## Python packages

The table covers the exact resolved Python environment. The final three entries
are conditional packages present in uv.lock but not installed in the audited
macOS environment. Full upstream copyright and license texts remain in each
package distribution.

| Package | Version | Upstream license |
|---|---:|---|
| annotated-doc | 0.0.5 | MIT |
| annotated-types | 0.8.0 | MIT |
| anyio | 4.15.1 | MIT |
| certifi | 2026.10.19 | MPL-2.0 |
| cffi | 2.1.1 | MIT-0 |
| click | 8.5.0 | BSD-3-Clause |
| colorama | 0.4.6 | BSD-3-Clause |
| dnspython | 2.9.0 | ISC |
| email-validator | 2.3.0 | Unlicense |
| fastapi | 0.154.0 | MIT |
| flatbuffers | 25.12.19 | Apache-2.0 |
| h11 | 0.16.0 | MIT |
| h3 | 4.5.0 | Apache-2.0 |
| httpcore | 1.0.9 | BSD-3-Clause |
| httpcore2 | 2.15.1 | BSD-3-Clause |
| httpx | 0.28.1 | BSD-3-Clause |
| httpx2 | 2.15.1 | BSD-3-Clause |
| httpx2-jsfetch | 1.0 | BSD-3-Clause |
| idna | 3.20 | BSD-3-Clause |
| iniconfig | 2.3.1 | MIT |
| numpy | 2.5.4 | BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0 |
| opentelemetry-api | 1.45.1 | Apache-2.0 |
| packaging | 26.3 | Apache-2.0 OR BSD-2-Clause |
| pluggy | 1.7.0 | MIT |
| psycopg | 3.3.6 | LGPL-3.0-only |
| psycopg-binary | 3.3.6 | LGPL-3.0-only |
| pycparser | 3.11 | BSD-3-Clause |
| pydantic | 2.14.1 | MIT |
| pydantic_core | 2.50.1 | MIT |
| Pygments | 2.21.0 | BSD-2-Clause |
| pyswisseph | 2.10.3.2 | AGPL-3.0-only |
| pytest | 9.1.1 | MIT |
| starlette | 1.9.0 | BSD-3-Clause |
| timezonefinder | 8.3.0 | MIT |
| timezonefinder-data | 1.2026.3 | ODbL-1.0 |
| truststore | 0.10.5 | MIT |
| typing-inspection | 0.4.4 | MIT |
| typing_extensions | 4.16.0 | PSF-2.0 |
| tzdata | 2026.5 | Apache-2.0 |
| uvicorn | 0.54.0 | BSD-3-Clause |

## JavaScript packages

The exact package/version inventory below comes from
frontend/package-lock.json. The lock contains 120 resolved entries, including
optional platform binaries. Runtime packages are React, React DOM, and Scheduler;
the remaining entries are build, type, test, or optional platform dependencies.
Full copyright and license texts remain in the upstream package distributions.

<details><summary>Apache-2.0 — 2 package(s)</summary>

- baseline-browser-mapping@2.11.30
- typescript@5.9.3

</details>

<details><summary>BSD-3-Clause — 1 package(s)</summary>

- source-map-js@1.2.2

</details>

<details><summary>CC-BY-4.0 — 1 package(s)</summary>

- caniuse-lite@1.0.30001817

</details>

<details><summary>ISC — 5 package(s)</summary>

- electron-to-chromium@1.5.461
- lru-cache@5.1.1
- picocolors@1.1.1
- semver@6.3.1
- yallist@3.1.1

</details>

<details><summary>MIT — 111 package(s)</summary>

- @babel/code-frame@7.29.7
- @babel/compat-data@7.29.7
- @babel/core@7.29.7
- @babel/generator@7.29.8
- @babel/helper-compilation-targets@7.29.7
- @babel/helper-globals@7.29.7
- @babel/helper-module-imports@7.29.7
- @babel/helper-module-transforms@7.29.7
- @babel/helper-plugin-utils@7.29.7
- @babel/helper-string-parser@7.29.7
- @babel/helper-validator-identifier@7.29.7
- @babel/helper-validator-option@7.29.7
- @babel/helpers@7.29.10
- @babel/parser@7.29.9
- @babel/plugin-transform-react-jsx-self@7.29.7
- @babel/plugin-transform-react-jsx-source@7.29.7
- @babel/template@7.29.7
- @babel/traverse@7.29.10
- @babel/types@7.29.8
- @esbuild/aix-ppc64@0.28.2
- @esbuild/android-arm64@0.28.2
- @esbuild/android-arm@0.28.2
- @esbuild/android-x64@0.28.2
- @esbuild/darwin-arm64@0.28.2
- @esbuild/darwin-x64@0.28.2
- @esbuild/freebsd-arm64@0.28.2
- @esbuild/freebsd-x64@0.28.2
- @esbuild/linux-arm64@0.28.2
- @esbuild/linux-arm@0.28.2
- @esbuild/linux-ia32@0.28.2
- @esbuild/linux-loong64@0.28.2
- @esbuild/linux-mips64el@0.28.2
- @esbuild/linux-ppc64@0.28.2
- @esbuild/linux-riscv64@0.28.2
- @esbuild/linux-s390x@0.28.2
- @esbuild/linux-x64@0.28.2
- @esbuild/netbsd-arm64@0.28.2
- @esbuild/netbsd-x64@0.28.2
- @esbuild/openbsd-arm64@0.28.2
- @esbuild/openbsd-x64@0.28.2
- @esbuild/openharmony-arm64@0.28.2
- @esbuild/sunos-x64@0.28.2
- @esbuild/win32-arm64@0.28.2
- @esbuild/win32-ia32@0.28.2
- @esbuild/win32-x64@0.28.2
- @jridgewell/gen-mapping@0.3.13
- @jridgewell/remapping@2.3.5
- @jridgewell/resolve-uri@3.1.2
- @jridgewell/sourcemap-codec@1.6.0
- @jridgewell/trace-mapping@0.3.31
- @napi-rs/lzma-linux-x64-gnu@1.5.1
- @rolldown/pluginutils@1.0.0-rc.3
- @rollup/rollup-android-arm-eabi@4.64.12
- @rollup/rollup-android-arm64@4.64.12
- @rollup/rollup-darwin-arm64@4.64.12
- @rollup/rollup-darwin-x64@4.64.12
- @rollup/rollup-freebsd-arm64@4.64.12
- @rollup/rollup-freebsd-x64@4.64.12
- @rollup/rollup-linux-arm-gnueabihf@4.64.12
- @rollup/rollup-linux-arm-musleabihf@4.64.12
- @rollup/rollup-linux-arm64-gnu@4.64.12
- @rollup/rollup-linux-arm64-musl@4.64.12
- @rollup/rollup-linux-loong64-gnu@4.64.12
- @rollup/rollup-linux-loong64-musl@4.64.12
- @rollup/rollup-linux-ppc64-gnu@4.64.12
- @rollup/rollup-linux-ppc64-musl@4.64.12
- @rollup/rollup-linux-riscv64-gnu@4.64.12
- @rollup/rollup-linux-riscv64-musl@4.64.12
- @rollup/rollup-linux-s390x-gnu@4.64.12
- @rollup/rollup-linux-x64-gnu@4.64.12
- @rollup/rollup-linux-x64-musl@4.64.12
- @rollup/rollup-openbsd-x64@4.64.12
- @rollup/rollup-openharmony-arm64@4.64.12
- @rollup/rollup-win32-arm64-msvc@4.64.12
- @rollup/rollup-win32-ia32-msvc@4.64.12
- @rollup/rollup-win32-x64-gnu@4.64.12
- @rollup/rollup-win32-x64-msvc@4.64.12
- @types/babel__core@7.20.5
- @types/babel__generator@7.27.0
- @types/babel__template@7.4.4
- @types/babel__traverse@7.28.0
- @types/estree@1.0.9
- @types/react-dom@19.3.0
- @types/react@19.3.0
- @vitejs/plugin-react@5.2.0
- browserslist@4.29.4
- convert-source-map@2.0.0
- csstype@3.2.3
- debug@4.4.3
- esbuild@0.28.2
- escalade@3.2.0
- fdir@6.5.0
- fsevents@2.3.3
- gensync@1.0.0-beta.2
- js-tokens@4.0.0
- jsesc@3.1.0
- json5@2.2.3
- ms@2.1.3
- nanoid@3.3.20
- node-releases@2.0.59
- picomatch@4.0.7
- postcss@8.5.31
- prettier@3.9.10
- react-dom@19.3.1
- react-refresh@0.18.0
- react@19.3.1
- rollup@4.64.12
- scheduler@0.28.0
- tinyglobby@0.2.17
- update-browserslist-db@1.3.4
- vite@7.3.7

</details>

## License references

- AGPL-3.0-only: https://www.gnu.org/licenses/agpl-3.0.html
- Apache-2.0: https://www.apache.org/licenses/LICENSE-2.0
- BSD, ISC, MIT, MIT-0, MPL-2.0, LGPL-3.0-only, PSF-2.0, Unlicense, Zlib,
  0BSD and CC0 license identifiers: https://spdx.org/licenses/
- CC-BY-4.0: https://creativecommons.org/licenses/by/4.0/
- ODbL-1.0: https://opendatacommons.org/licenses/odbl/1-0/


