# aria2 (bundled binary)

This application bundles the `aria2c` binary and communicates with it over its
JSON-RPC interface as a **separate process** (no static/dynamic linking).

- **Project:** aria2 — https://aria2.github.io/
- **Source code:** https://github.com/aria2/aria2
- **License:** GNU GPL v2 or later (see `LICENSE` in this folder)

aria2 is free and open source. Redistributing the binary is permitted under the
GPL provided the license text and a way to obtain the corresponding source are
included — both of which are satisfied by this folder and the link above.

Because stz-downloader only invokes `aria2c` as an external RPC process, it is
"mere aggregation" under the GPL and does not impose the GPL on this project's
own source code.

## How to obtain the binary

Run `scripts/fetch_aria2.py` (or download from the GitHub releases above) to
place `aria2c.exe` in this folder. The binary is intentionally **not** checked
into version control.
