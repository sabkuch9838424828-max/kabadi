# Architecture

## 1. Components

```
 Collector PWA (port 12000)          Ops web (port 12001)
 +-------------------------+         +------------------------------+
 | React + Vite + PWA      |         | React + Vite                 |
 | Dexie (IndexedDB cache) |         | /console  recycler console   |
 | /api proxy -------------+---+     | /dashboard Ministry dashboard|
 +-------------------------+   |     | /api proxy ------------------+--+
                               |     +------------------------------+  |
                               v                                       v
                       +----------------------------------------------+
                       | FastAPI  app.main:app  (port 8000)           |
                       |  /api/v1/{auth,collectors,lots,recyclers,    |
                       |           recycler,prices,ml,admin}          |
                       |  services: valuation - pricing - matching -  |
                       |            analytics - serializers           |
                       |  ml: classifier - stoichiometry - anomaly    |
                       +----------------------------------------------+
                                        | SQLAlchemy 2.x
                                        v
                       +----------------------------------------------+
                       | PostgreSQL + PostGIS                         |
                       +----------------------------------------------+
```

All HTTP traffic from the browsers goes to the frontend origin and is reverse
proxied to the backend by Vite (`/api` to `127.0.0.1:8000`), so CORS and port
exposure stay simple.

## 2. Layer responsibilities

| Layer | Location | Responsibility |
| --- | --- | --- |
| Routers | `backend/app/api/v1/*` | HTTP shape, auth deps, validation, error codes |
| Dependencies | `backend/app/api/deps.py` | JWT decode + role gates (`current_collector`, `current_recycler`, `require_role`) |
| Services | `backend/app/services/*` | Business logic, pure-ish and unit-testable |
| ML | `backend/app/ml/*` | Classifier, stoichiometry, anomaly detection |
| Models | `backend/app/models/models.py` | SQLAlchemy ORM / schema |
| Schemas | `backend/app/schemas/schemas.py` | Pydantic request/response contracts |

## 3. Data model (tables)

| Table | Purpose |
| --- | --- |
| `users` | Auth principal; `role` in {collector, recycler, admin} |
| `collectors` | Collector profile, district, preferred language, PostGIS point |
| `recyclers` | Facility, accepted categories, CPCB status, capacity, service radius, offered rates |
| `material_prices` | Per-category price rows (`source` = recycler or msp_benchmark), benchmark flag |
| `lots` | A collected batch: declared/verified weight, estimate, recovery score, mineral JSON, quoted (per-kg) & final price, status |
| `handovers` | Photo ref, PostGIS GPS point, timestamp, unique reference number, recycler confirmation |
| `transactions` | Payment for a lot (amount, cash/upi, pending/paid) |
| `material_compositions` | Stoichiometric ratio ranges per category/element (+ CO2 factor, critical flag) |
| `price_history` | Price snapshots - trend arrows + anomaly detector baseline |
| `fraud_flags` | Price anomalies and weight anomalies |
| `audit_log` | Actor, action, entity, JSON detail - EPR compliance trail |

### Lot lifecycle

```
created --match--> matched --handover--> handover --verify--> verified --pay--> paid
                                        \------------decline----> declined
```

## 4. Valuation pipeline

`evaluate_lot(db, category, weight, location)`:

1. `pricing.effective_price` resolves the best per-kg price for the category and
   district (recycler-offered price, falling back to the MSP benchmark, then
   national).
2. `stoichiometry.evaluate` applies published composition ratios to the batch
   weight to estimate critical-mineral quantities (kg), an estimated material
   value, an estimated CO2 saving, and computes the **Recovery Score** (0-100)
   from critical-mineral richness and value density.
3. The result carries a machine-readable `composition_basis` plus the
   disclaimer text surfaced verbatim in the UI.

Estimates are approximations, not assays. The classifier preferably loads a
fine-tuned checkpoint (`MODEL_PATH`); otherwise it uses ImageNet-pretrained
MobileNetV3 mapped onto e-waste categories.

## 5. Trust layer

* `quoted_price` is stored as a **per-kg rate**.
* On recycler verification: `final_price = quoted_price x verified_weight`
  (the collector's `declared_weight` is preserved separately for comparison).
* A declared-vs-verified delta beyond the configured tolerance creates a
  `FraudFlag(kind="weight_anomaly")`, visible on the Ministry dashboard.
* Handovers are the EPR chain-of-custody record: GPS + timestamp + photo ref +
  unique reference number.

## 6. Offline-first design

* Cached in IndexedDB: the collector's lots, the price board and the recycler
  list, each with a `*_at` freshness stamp.
* Lot creation writes locally first (`sync_state = pending`) and queues the
  payload. `POST /lots/sync` accepts a batch and is **idempotent by
  `client_uuid`**, so retries never duplicate lots.
* The price board renders stale cached data with an offline banner when the
  network is unavailable.

## 7. Security

* JWT (HS256) bearer tokens; role claims enforced per route.
* Passwords hashed with bcrypt via passlib.
* `SECRET_KEY` and DB credentials come from environment / `.env` (never
  committed).
* Unhandled exceptions return a generic 500; details are logged server-side.
* Handover/verification actions are constrained to the assigned recycler.
