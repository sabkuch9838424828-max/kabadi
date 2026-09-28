# AGENTS.md

Repository knowledge for Kabadiwala Connect (SIH26229). See `README.md`,
`docs/ARCHITECTURE.md` and `docs/API.md` for the full picture.

## Layout

* `backend/` — FastAPI app (`app.main:app`), SQLAlchemy + PostGIS, ML valuation.
* `collector-pwa/` — offline-first React PWA for collectors (port 12000).
* `ops-web/` — React/Vite recycler console (`/console`) + Ministry dashboard
  (`/dashboard`) on port 12001.

## Commands

```bash
# backend
cd backend && . .venv/bin/activate
python -m scripts.seed                 # create schema + demo data (idempotent)
uvicorn app.main:app --host 0.0.0.0 --port 8000
python -m scripts.e2e_test             # 74 checks, purges its own artifacts
python -m scripts.purge_e2e            # remove e2e artifacts only

# frontends
cd collector-pwa && npm run dev        # 12000
cd ops-web && npm run build && npm run preview   # 12001
```

Both frontends proxy `/api` to `http://127.0.0.1:8000`
(`VITE_PROXY_TARGET` overrides).

## Conventions & invariants

* `lots.quoted_price` is a **per-kg rate**, not a lot total.
  On verification: `final_price = quoted_price x verified_weight`.
  Payment is always computed on the **verified** weight, never the declared one.
* `POST /lots/sync` is idempotent by `client_uuid` — retries must not duplicate.
* Handovers require GPS + timestamp + photo ref and issue a unique reference.
* Only CPCB-`authorized` recyclers accepting the category may receive a lot.
* Critical-mineral figures are **estimates** from published stoichiometric
  ratios; never present them as measured values.
* Secrets live in `backend/.env` (git-ignored); `.env.example` is the template.

## Demo accounts

* admin — `admin@kabadiwala.gov.in` / `Admin@12345`
* recycler — `greenloop@recycler.in` / `Recycler@123`
* collector — `ravi@kabadiwala.in` / `Collector@123`
