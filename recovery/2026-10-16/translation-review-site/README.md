# 译文审阅台

Buildless, public, no-login, read-only translation evidence viewer. Deploy `dist/` as static assets. No build or package installation is required. All JSON files are selected by the visitor and processed locally; no report content is bundled except a clearly marked two-entry synthetic demo.

## Use

Open the HTTPS site, choose or drop one supported JSON report (maximum 10 MiB), browse English/Chinese evidence, open full context, and mark entries read or undo. Search and unread/read filters narrow the queue. Export reading progress to JSON before changing browser/device. Import merges completed entries and requires the same document-content SHA-256. Closing a report clears the visible document from memory; browser-local reading markers remain. No source or translated text is editable.

Supported inputs: audit `schemaVersion: 1` / `findings`, `pbres-config-draft-v1`, `mechanic-quantity-scopes-v1`, and full check envelopes. These are snapshots, not rerun checks, signatures, approval, or semantic verification. Reading completion does not approve anything.

## Privacy and safety

No backend, accounts, analytics, uploads, external assets, fetch requests, imported HTML execution, or third-party fonts. CSP disallows network connections and restricts scripts/styles to same origin. Rendering uses text nodes and code-point slices. Inputs are validated before replacing the current report. Async generations prevent late file reads from overwriting a newer selection or progress edit. Progress storage contains only a document hash and completion IDs, never original/translated text. The hosting service still receives ordinary page requests. Browser-local content is not encrypted from other people with access to that browser profile.

## Checks

`node --test model.test.mjs app.test.mjs`

`node --check dist/app.mjs && node --check dist/model.mjs`

Unit/DOM-simulation checks do not replace real-browser visual and interaction QA. No browser dependencies are installed. Root publisher handles native Sites registration, manifest, source synchronization, deployment, and live browser verification.

## Compatibility limits

Draft preview digests follow Python Unicode key ordering and require safe integer numeric fields; floating-point or unsafe-integer draft previews are rejected instead of risking a misleading hash result. A bounded Pandoc AST reader supports the existing common heading/paragraph/inline cases. Unknown AST structures fall back to explicitly labeled raw text without invented highlights. The browser does not reparse the raw Markdown or verify that the saved AST still describes current project files. Exported progress is this site's own format and does not claim compatibility with the separate offline HTML renderer's progress format.
