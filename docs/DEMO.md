# CareTwin AI — reproducible demo

This is the shortest reliable path to run and demonstrate CareTwin AI on this
Windows machine. No real patient data is used. CareTwin is a synthetic demo, not a
medical device, and the demo identity is a header rather than authentication.

## 1. Prerequisites

| Requirement | Verified here |
| --- | --- |
| Node.js | v22.22.3 (needs 20.9+) |
| npm | ships with Node |
| Python | 3.14.4 (needs 3.11+) |
| Tesseract OCR | `C:\Program Files\Tesseract-OCR\tesseract.exe` (optional; only scanned pages need it) |
| Free disk | ~1 GB (next build cache + SQLite) |

The repository ships `package-lock.json` and `apps/api/requirements.txt`; keep them.

## 2. Install once

```powershell
cd "C:\Users\ddsai\Downloads\CareTwin AI"
npm install

cd apps\api
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
cd ..\..
```

If the venv already exists, skip the two Python lines.

## 3. Configure the model key (optional)

Deterministic extraction, comparison, records and the Digital Twin work without a
key. Without `GEMINI_API_KEY` the UI shows "AI unavailable" and the API returns
`503 ai_not_configured` — that is expected, not a defect. **No genuine Gemini
response has been recorded in this checkout**; provider behaviour is covered by
mocked, automated tests only. See `docs/AI_ARCHITECTURE.md`.

Create the local env file **without putting the key in command history**:

```powershell
cd "C:\Users\ddsai\Downloads\CareTwin AI"
notepad .env
```

In Notepad paste:

```ini
GEMINI_API_KEY=your-own-key-here
CARETWIN_AI_MODEL=gemini-3.8-flash
```

Save and close. `.env` is already gitignored (`.env`, `.env.local`, `.env.*.local`).
Do not use `Set-Content`/`$env:GEMINI_API_KEY = "…"` for the real key: PowerShell
records those commands in its history file. If you must use the shell, clear history
afterwards with `Clear-History` and remove
`$env:APPDATA\Microsoft\Windows\PowerShell\PSReadLine\ConsoleHost_history.txt`.

Get a key from <https://aistudio.google.com/apikey>. Never commit `.env`, never paste
the key into chat, and never prefix it with `NEXT_PUBLIC_`.

## 4. Start the app

Terminal 1 (API):

```powershell
cd "C:\Users\ddsai\Downloads\CareTwin AI"
$env:CARETWIN_TESSERACT_CMD = "C:\Program Files\Tesseract-OCR\tesseract.exe"   # optional
npm run dev:api
```

The first start creates and seeds `data\demo\caretwin.db`.

Terminal 2 (web):

```powershell
cd "C:\Users\ddsai\Downloads\CareTwin AI"
npm run dev:web
```

Open <http://localhost:3000>. For a production-style demo instead:

```powershell
npm run build --workspace @caretwin/web
npm run start --workspace @caretwin/web -- -p 3000 -H 127.0.0.1
```

Health checks: <http://127.0.0.1:8000/api/v1/health> and
<http://127.0.0.1:8000/api/v1/ai/status>.

## 5. Demo script (about 10 minutes)

1. **Landing** (`/`) — read the safety statement.
2. **Role choice** (`/demo`) — pick *Maya Rao — patient*.
3. **Dashboard** (`/workspace`) — recovery position, open alerts, next actions.
4. **Documents** (`/workspace/documents`) — upload `SYNTHETIC-*.pdf` or any
   synthetic PDF; watch extraction (pypdf for digital text, OCR for scans), then open
   *Original & pages* to show the page-level source. Point out the AI panel: with no
   key it says "AI unavailable" and the deterministic extraction is still complete.
   With a key, press *Generate AI explanation* and read summary, results with
   printed ranges, uncertainty, citations and the "not a diagnosis" footer.
5. **Prescription tab** — medicine name, written dose, frequency, timing, duration,
   unreadable warnings. CareTwin never proposes a new prescription.
6. **Comparison** — two reports of the same test in the same unit show a numeric
   difference and nothing more; different units are listed as not comparable.
7. **Assistant** (`/workspace/assistant`) — ask "Explain my latest blood report".
   Show the badge: `deterministic records` (no key) or `AI explanation · grounded`
   (key). Facts, sources with pages and verification state are always listed.
   Ask about a test that is not in the records to show the honest gap.
8. **Digital Twin** (`/workspace/twin`) — the model rotates continuously; drag to
   rotate, scroll to zoom, pause/resume, switch system layers. Version, status and
   verified findings come from the server; unverified values are never shown as
   confirmed conditions.
9. **Clinician** — switch to *Dr. Nandini Iyer*, open *Monitoring & Alerts*,
   acknowledge/resolve an alert, then verify or reject an extracted item in
   Documents. Only a clinician can do this, and every action is audited.
10. **Caregiver boundary** — switch to *Priya Rao* (consent revoked): twin and
    documents are refused with an explicit consent message.

## 6. Reset the demo

```powershell
# Stop the API first
Remove-Item "data\demo\caretwin.db*" -ErrorAction SilentlyContinue
npm run dev:api
```

Uploaded files live in `data\documents\` (gitignored) and are not removed by the
database reset. Remove that folder only if you want a clean upload history.

## 7. Verification commands

```powershell
# Backend (controlled, use D: temp on constrained machines)
$env:TEMP="D:\caretwin-caches\tmp"; $env:TMP="D:\caretwin-caches\tmp"
.\apps\api\.venv\Scripts\python.exe -m pytest apps\api\tests -q -p no:cacheprovider

# Deterministic intelligence checks (65 checks; run twice; isolated API/DB/storage, demo DB untouched)
.\apps\api\.venv\Scripts\python.exe scripts\verify_intelligence.py

# Frontend gates
npm run typecheck --workspace @caretwin/web
npm run lint --workspace @caretwin/web
$env:NODE_OPTIONS="--max-old-space-size=2048"; npm run build --workspace @caretwin/web

# Browser suite (starts its own API on port 8000 with a throwaway DB)
npx playwright test tests/e2e/caretwin.spec.ts tests/e2e/phase7.spec.ts --workers=1
```

The Playwright API server forces an empty `GEMINI_API_KEY` and uses an isolated
test DB/document storage (`data/e2e/`), so browser tests do not spend provider
credits or write to the demo DB. (Phase 17.1 fixed e2e document-storage isolation
in `scripts/e2e-api-server.mjs`; two orphan PDFs from a prior run may remain in
`data/documents/pat_maya/` and were not removed.) On memory/disk-constrained
machines, run gates sequentially (no parallel builds/tests), keep temp/caches on
D:, and ensure no leftover dev servers are listening on 3000/8000.

**Phase 17.1 local results (controlled rerun):** backend 101 passed, 3 skipped;
intelligence 65/65 twice; typecheck/lint pass; fresh production build pass;
Playwright 7/7 pass. `npm audit --omit=dev` still reports unresolved bundled
`postcss@8.4.31` in `next@15.5.29` (breaking Next 16 fix path). Demo DB counts
unchanged (246/938/674/72/0/4/1); document storage 83 files.

## 8. Synthetic cleanup review

```powershell
.\apps\api\.venv\Scripts\python.exe scripts\cleanup_synthetic.py
```

Dry-run only. It selects documents whose filename starts with `SYNTHETIC-` (or a
marker you pass), lists the exact ids, and never touches the audit trail. Deletion
requires `--confirm`, which should only be run after you approve the list.

## 9. Known limitations

- Demo header identity (`X-Demo-User-Id`) is not authentication; there are no
  sessions, MFA or password flows.
- Rate limits are per-process and in memory.
- SQLite and local file storage suit a single-machine demo only.
- Frontend `next/postcss` advisories remain unresolved without a breaking Next upgrade.
- Scanned documents depend on Tesseract; extraction and OCR can misread digits, so
  every extracted item stays unverified until a clinician reviews it.
- No live Gemini call is verified in this checkout unless you add your own key.
- Not a diagnosis, not prescribing, not clinically validated, not HIPAA/GDPR
  certified. See `docs/SECURITY.md`.

## 10. Safe shutdown

Press `Ctrl+C` in each terminal, then confirm nothing is still listening:

```powershell
Get-NetTCPConnection -LocalPort 3000,8000 -State Listen -ErrorAction SilentlyContinue
```

Do not delete `data\demo\caretwin.db` unless you intend to reset the demo; deleting
`data\documents\` permanently removes uploaded files.
