# API Reference

Base URL: `/api/v1` (via the frontend proxy) or `http://localhost:8000/api/v1`
directly. Interactive docs: `/docs` (Swagger) and `/redoc`.

Authentication is JWT bearer: send `Authorization: Bearer <access_token>`.
Roles: `collector`, `recycler`, `admin`.

## Meta

| Method | Path | Auth | Description |
| --- | --- | --- | --- |
| GET | `/health` | none | Health + DB connectivity |
| GET | `/` | none | Service banner |

## Auth (`/auth`)

| Method | Path | Auth | Description |
| --- | --- | --- | --- |
| POST | `/auth/token` | none | OAuth2 password login, returns `{access_token, role, ...}` |
| POST | `/auth/register` | none | Register a collector/recycler account |
| GET | `/auth/me` | any | Current user + linked profile |

## Collectors (`/collectors`)

| Method | Path | Auth | Description |
| --- | --- | --- | --- |
| POST | `/collectors/me` | collector | Create/update collector profile |
| GET | `/collectors/me` | collector | Read profile |
| GET | `/collectors/me/ledger` | collector | Earnings ledger (totals + transactions) |

## Lots (`/lots`)

| Method | Path | Auth | Description |
| --- | --- | --- | --- |
| POST | `/lots` | collector | Create a lot; runs valuation instantly |
| POST | `/lots/sync` | collector | Bulk idempotent upload of offline lots (keyed by `client_uuid`) |
| GET | `/lots` | collector | List the collector's lots |
| GET | `/lots/{lot_id}` | collector | Lot detail (minerals, handover, transaction) |
| POST | `/lots/{lot_id}/valuation` | collector | Re-run valuation |
| GET | `/lots/{lot_id}/matches` | collector | Ranked authorized-recycler matches |
| POST | `/lots/{lot_id}/match` | collector | Assign a recycler (sets status `matched`, records per-kg `quoted_price`) |
| POST | `/lots/{lot_id}/handover` | collector | Record digital receipt: photo + GPS + timestamp |

## Recyclers (`/recyclers`)

| Method | Path | Auth | Description |
| --- | --- | --- | --- |
| GET | `/recyclers` | any | List recyclers |
| GET | `/recyclers/match` | collector | Stateless matching by category/location |
| POST | `/recyclers/me` | recycler | Create/update recycler profile |
| GET | `/recyclers/me` | recycler | Read profile |

## Recycler console (`/recycler`)

| Method | Path | Auth | Description |
| --- | --- | --- | --- |
| GET | `/recycler/lots` | recycler | Incoming lots assigned to the recycler |
| POST | `/recycler/lots/{lot_id}/verify` | recycler | Record verified weight; `final_price = per-kg rate x verified`; confirms handover; pending transaction |
| POST | `/recycler/lots/{lot_id}/pay` | recycler | Mark the transaction paid (cash/upi) |
| POST | `/recycler/lots/{lot_id}/decline` | recycler | Decline a lot |
| GET | `/recycler/handovers` | recycler | Handover chain-of-custody list |
| GET | `/recycler/history` | recycler | Settled/deal history |

## Prices (`/prices`)

| Method | Path | Auth | Description |
| --- | --- | --- | --- |
| GET | `/prices/board` | none | Voice-friendly price board (category, best rate, benchmark, trend) |
| GET | `/prices/history/{category}` | none | Price trend series |
| POST | `/prices/anomaly-check` | any | Check a quoted price against history |
| POST | `/prices` | recycler | Publish a per-kg rate |
| GET | `/prices/mine` | recycler | The recycler's published rates |

## ML (`/ml`)

| Method | Path | Auth | Description |
| --- | --- | --- | --- |
| GET | `/ml/model-info` | none | Classifier name + availability |
| GET | `/ml/valuation-config` | none | Categories, composition basis, disclaimer |
| POST | `/ml/classify` | any | Classify a material photo (multipart upload) |
| GET | `/ml/valuation` | any | Ad-hoc valuation for a category/weight |

## Admin / Ministry (`/admin`)

| Method | Path | Auth | Description |
| --- | --- | --- | --- |
| GET | `/admin/recyclers` | admin | All recyclers (optional `?status=`) |
| PATCH | `/admin/recyclers/{id}/authorization` | admin | Approve/suspend (requires a registration number) |
| POST | `/admin/prices/benchmark` | admin | Set the MSP benchmark price |
| GET | `/admin/prices` | admin | All price rows |
| GET | `/admin/analytics` | admin | District/category aggregates, KPIs |
| GET | `/admin/fraud-flags` | admin | Weight + price anomaly flags |
| GET | `/admin/audit-log` | admin | EPR compliance audit trail |

## Status codes

* `401` — missing/invalid token
* `403` — authenticated but wrong role
* `404` — resource not found / not assigned to the caller
* `409` — invalid state transition (e.g. verifying an unconfirmed handover, double verify, unauthorized recycler handover)
* `422` — validation error (Pydantic) or domain rule (e.g. non-positive weight)
* `500` — generic server error (details logged, never returned)
