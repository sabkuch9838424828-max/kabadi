# Kabadiwala Connect — SIH26229

Composition-aware e-waste collection platform that brings the informal
**kabadiwala** (waste collector) into the formal **EPR** recycling chain.

> **"Weighing nahi, Looking Inside"** — value is driven by what is *inside* a
> lot (critical minerals), not only by its weight.

The repository contains three deployable pieces plus a FastAPI backend:

| Component | Path | Port | Purpose |
| --- | --- | --- | --- |
| Backend API | `backend/` | 8000 | FastAPI + PostgreSQL/PostGIS, ML valuation, auth |
| Collector PWA | `collector-pwa/` | 12000 | Offline-first app for collectors (Hindi/Marathi/English) |
| Ops web | `ops-web/` | 12001 | Recycler console (`/console`) + Ministry dashboard (`/dashboard`) |

---

## 1. Core capabilities

1. **Composition-aware valuation** — each material category has published
   stoichiometric mineral ranges (JNARDDC/industry estimates). A lot gets an
   estimated value, a **Recovery Score** (0–100) and an estimated CO₂ saving.
   All figures are *estimates*, explicitly labelled as such in the UI.
2. **Declared vs verified trust layer** — the collector declares a weight; the
   recycler records the physically verified weight. Payment is computed on the
   **verified** weight only. Large deltas raise a fraud flag.
3. **Digital receipt** — handover capture stores GPS + timestamp + photo
   reference and issues a human-readable reference number
   (`KC-<district>-<yyyymmddhhmmss>-<suffix>`).
4. **EPR / audit compliance** — every authorization change, benchmark update and
   fraud event is written to an immutable-style audit log; handovers form the
   EPR chain-of-custody trail.
5. **MSP pricing + recycler matching** — Ministry of Mines benchmark prices per
   category/district; lots are matched only to **CPCB-authorized** recyclers that
   accept the category, ranked by distance / offered rate / capacity.
6. **Offline-first collector PWA** — lots, price board and recycler list are
   cached in IndexedDB (Dexie). Lots created offline are queued and synced
   idempotently (by `client_uuid`) when connectivity returns.
7. **Analytics** — district heatmap, per-category aggregates, trend history and
   fraud flags for the Ministry dashboard.

---

## 2. Quick start

### Prerequisites

* PostgreSQL with the **PostGIS** extension
* Python 3.11+
* Node.js 18+

### 2.1 Database

```bash
sudo service postgresql start        # or your platform's equivalent
sudo -u postgres psql -c "CREATE USER kabadiwala WITH PASSWORD 'kabadiwala_dev_pw';"
sudo -u postgres psql -c "CREATE DATABASE kabadiwala_connect OWNER kabadiwala;"
sudo -u postgres psql -d kabadiwala_connect -c "CREATE EXTENSION IF NOT EXISTS postgis;"
```

### 2.2 Backend

```bash
cd backend
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env                 # then edit values (never commit .env)
python -m scripts.seed               # create schema + demo data (idempotent)
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

* API docs: <http://localhost:8000/docs>
* Health:   <http://localhost:8000/api/v1/health>

### 2.3 Collector PWA (port 12000)

```bash
cd collector-pwa
npm install
npm run dev            # development
# or: npm run build && npm run preview
```

### 2.4 Ops web (port 12001)

```bash
cd ops-web
npm install
npm run dev            # development
# or: npm run build && npm run preview
```

Both frontends proxy `/api` to `http://127.0.0.1:8000` (override with
`VITE_PROXY_TARGET`), so the browser never talks to the backend port directly.

---

## 3. Demo accounts

Created by `python -m scripts.seed` (username = email, password shown):

| Role | Email | Password | Entry point |
| --- | --- | --- | --- |
| Ministry / Admin | `admin@kabadiwala.gov.in` | `Admin@12345` | http://localhost:12001/dashboard |
| Recycler | `greenloop@recycler.in` (also `ecorecycle@recycler.in`, …) | `Recycler@123` | http://localhost:12001/console |
| Collector | `ravi@kabadiwala.in` (also `sunita@…`, …) | `Collector@123` | http://localhost:12000 |

---

## 4. End-to-end demo flow

1. **Collector signs in** → onboarding (name, district, language).
2. **New lot** (`/add`): pick a category, enter weight, capture a photo →
   instant valuation, mineral breakdown and Recovery Score (works offline too).
3. **Match** the lot to a nearby authorized recycler.
4. **Handover**: capture photo + GPS + timestamp → digital receipt reference.
5. **Recycler console**: the incoming lot appears → enter the **verified**
   weight → payment is recomputed on the verified weight → mark paid (cash/UPI).
6. **Collector earnings** ledger reflects the settlement.
7. **Ministry dashboard**: district heatmap, category aggregates, audit trail
   and any fraud flags raised by declared-vs-verified gaps.

---

## 5. Tests

The backend ships an end-to-end suite that exercises the whole flow against a
running API and then returns the database to a demo-clean state:

```bash
cd backend && . .venv/bin/activate
python -m scripts.e2e_test        # 74 checks across 16 sections
```

`python -m scripts.purge_e2e` removes any e2e artifacts without touching seeded
demo data.

---

## 6. Environment variables

See `backend/.env.example`. Key settings:

| Variable | Description |
| --- | --- |
| `DATABASE_URL` | SQLAlchemy URL to the PostGIS database |
| `SECRET_KEY` | JWT signing secret — **must** be a long random value in production |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Token lifetime (default 1440) |
| `CORS_ORIGINS` | Comma-separated allowed origins for both frontends |
| `MODEL_PATH` | Optional fine-tuned classifier checkpoint (`.pt`) |
| `ALLOW_MODEL_DOWNLOAD` | Allow downloading pretrained weights when `MODEL_PATH` is unset |

Frontend (optional): `VITE_PROXY_TARGET` overrides the `/api` proxy target.

---

## 7. Documentation

* [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — system design, data model, request flow.
* [`docs/API.md`](docs/API.md) — endpoint reference.

## 8. Notes & limitations

* Critical-mineral quantities and CO₂ savings are **estimates from published
  stoichiometric ratios**, not laboratory assays. The UI states this explicitly.
* The material classifier uses an ImageNet-pretrained MobileNetV3 plus the
  documented e-waste category map unless a fine-tuned checkpoint is supplied.
* Payment settlement is recorded (cash/UPI) but does not integrate a live
  payment gateway; it is the reviewer-facing ledger.
