"""End-to-end integration test of the documented Kabadiwala Connect workflow.

Runs against the live API (default http://127.0.0.1:8000) and exercises the
full collector -> recycler -> admin chain exactly as described in the
SIH26229 documentation demo flow (section 11).

Usage:  python -m scripts.e2e_test [base_url]
"""
from __future__ import annotations

import io
import random
import sys
import time

import httpx

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
API = f"{BASE}/api/v1"

PASS: list[str] = []
FAIL: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    if cond:
        PASS.append(name)
        print(f"  [PASS] {name}")
    else:
        FAIL.append(f"{name} :: {detail}")
        print(f"  [FAIL] {name} :: {detail}")


def auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def main() -> int:
    client = httpx.Client(timeout=60.0)
    rnd = random.randint(1000, 9999)

    print("\n=== 0. Meta ===")
    r = client.get(f"{API}/health")
    check("health ok", r.status_code == 200 and r.json()["database"], r.text[:200])
    r = client.get(f"{API}/ml/model-info")
    check("classifier available", r.json().get("available") is True, r.text[:200])
    check("model-info honesty flag", r.json().get("is_estimate") is True)

    print("\n=== 1. Auth / RBAC (3 roles) ===")
    rc = client.post(
        f"{API}/auth/register",
        json={
            "email": f"e2e_collector_{rnd}@test.in",
            "password": "Collector@123",
            "full_name": "E2E Collector",
            "role": "collector",
        },
    )
    check("collector register", rc.status_code == 201, rc.text[:300])
    collector_token = rc.json().get("access_token", "")

    rr = client.post(
        f"{API}/auth/register",
        json={
            "email": f"e2e_recycler_{rnd}@test.in",
            "password": "Recycler@123",
            "full_name": "E2E Recycler",
            "role": "recycler",
        },
    )
    check("recycler register", rr.status_code == 201, rr.text[:300])
    recycler_token = rr.json().get("access_token", "")

    ra = client.post(
        f"{API}/auth/token",
        data={"username": "admin@kabadiwala.gov.in", "password": "Admin@12345"},
    )
    check("admin login", ra.status_code == 200, ra.text[:300])
    admin_token = ra.json().get("access_token", "")

    r = client.post(
        f"{API}/auth/token", data={"username": "ravi@kabadiwala.in", "password": "wrong"}
    )
    check("bad password rejected", r.status_code == 401)

    r = client.get(f"{API}/collectors/me/ledger")
    check("unauthenticated ledger blocked", r.status_code == 401)

    r = client.get(f"{API}/admin/analytics", headers=auth_header(collector_token))
    check("RBAC: collector cannot read admin analytics", r.status_code == 403)

    r = client.get(f"{API}/recycler/lots", headers=auth_header(collector_token))
    check("RBAC: collector cannot read recycler console", r.status_code == 403)

    r = client.get(f"{API}/auth/me", headers=auth_header(collector_token))
    check("auth/me works", r.status_code == 200 and r.json()["user"]["role"] == "collector", r.text[:200])

    print("\n=== 2. Collector onboarding ===")
    r = client.post(
        f"{API}/collectors/me",
        headers=auth_header(collector_token),
        json={
            "preferred_language": "mr",
            "display_name": "E2E Collector",
            "latitude": 18.5204,
            "longitude": 73.8567,
            "district": "Pune",
            "state": "Maharashtra",
        },
    )
    check("collector profile upsert", r.status_code == 200 and r.json()["preferred_language"] == "mr", r.text[:300])

    print("\n=== 3. Recycler onboarding + authorization (admin) ===")
    r = client.post(
        f"{API}/recyclers/me",
        headers=auth_header(recycler_token),
        json={
            "name": "E2E Green Recyclers",
            "latitude": 18.53,
            "longitude": 73.87,
            "district": "Pune",
            "state": "Maharashtra",
            "materials_accepted": ["PCB", "battery", "cable"],
            "cpcb_registration_number": f"CPCB/EW/2025/E2E-{rnd}",
            "service_area_radius_km": 50,
            "capacity_kg_per_day": 3000,
            "pickup_available": True,
        },
    )
    check("recycler profile upsert", r.status_code == 200, r.text[:300])
    recycler_id = r.json().get("recycler_id")

    r = client.patch(
        f"{API}/admin/recyclers/{recycler_id}/authorization",
        headers=auth_header(admin_token),
        json={"authorization_status": "authorized", "note": "CPCB verified"},
    )
    check("admin authorizes recycler", r.status_code == 200 and r.json()["authorization_status"] == "authorized", r.text[:300])

    r = client.patch(
        f"{API}/admin/recyclers/{recycler_id}/authorization",
        headers=auth_header(recycler_token),
        json={"authorization_status": "authorized"},
    )
    check("RBAC: recycler cannot self-authorize", r.status_code == 403)

    print("\n=== 4. Recycler publishes a rate ===")
    r = client.post(
        f"{API}/prices",
        headers=auth_header(recycler_token),
        json={"material_category": "PCB", "location": "Pune", "buying_price": 255.0},
    )
    check("recycler publishes rate", r.status_code == 201, r.text[:300])

    r = client.post(
        f"{API}/prices",
        headers=auth_header(recycler_token),
        json={"material_category": "PCB", "location": "Pune", "buying_price": 99999.0},
    )
    check("anomalous rate rejected", r.status_code == 422, r.text[:300])

    print("\n=== 5. Price board (voice-friendly, public) ===")
    r = client.get(f"{API}/prices/board")
    check("price board public", r.status_code == 200 and len(r.json()) >= 8, r.text[:200])
    board = {b["material_category"]: b for b in r.json()}
    check("board has trend field", board["PCB"]["trend"] in {"up", "down", "flat"})
    check("board marked as estimate", board["PCB"]["is_estimate"] is True)

    print("\n=== 6. AI classification ===")
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (224, 224), (30, 120, 60)).save(buf, format="JPEG")
    buf.seek(0)
    r = client.post(
        f"{API}/ml/classify", files={"file": ("board.jpg", buf.getvalue(), "image/jpeg")}
    )
    check("classify returns category", r.status_code == 200 and "material_category" in r.json(), r.text[:300])
    check("classify carries disclaimer", r.json().get("is_estimate") is True)

    r = client.post(f"{API}/ml/classify", files={"file": ("x.txt", b"hello", "text/plain")})
    check("classify rejects non-image", r.status_code == 415)

    print("\n=== 7. Create lot -> instant valuation + Recovery Score ===")
    client_uuid = f"e2e-{rnd}-lot1"
    r = client.post(
        f"{API}/lots",
        headers=auth_header(collector_token),
        json={
            "client_uuid": client_uuid,
            "material_category": "PCB",
            "declared_weight": 12.5,
            "latitude": 18.5204,
            "longitude": 73.8567,
            "district": "Pune",
            "capture_mode": "online",
        },
    )
    check("lot created", r.status_code == 201, r.text[:300])
    lot = r.json()
    lot_id = lot["lot_id"]
    check("valuation computed", float(lot["estimated_value"]) > 0, str(lot.get("estimated_value")))
    check("recovery score 0-100", 0 <= float(lot["recovery_score"] or -1) <= 100, str(lot.get("recovery_score")))
    check("mineral estimate present (Cu)", "Cu" in (lot["mineral_estimate"] or {}).get("minerals", {}), str(lot.get("mineral_estimate"))[:200])
    check("estimate disclaimer stored", bool((lot["mineral_estimate"] or {}).get("disclaimer")))

    r2 = client.post(
        f"{API}/lots",
        headers=auth_header(collector_token),
        json={"client_uuid": client_uuid, "material_category": "PCB", "declared_weight": 12.5},
    )
    check("lot create idempotent on client_uuid", r2.json()["lot_id"] == lot_id)

    r = client.post(
        f"{API}/lots",
        headers=auth_header(collector_token),
        json={"material_category": "banana", "declared_weight": 5},
    )
    check("invalid category rejected", r.status_code == 422)

    r = client.post(
        f"{API}/lots",
        headers=auth_header(collector_token),
        json={"material_category": "PCB", "declared_weight": -5},
    )
    check("negative weight rejected", r.status_code == 422)

    print("\n=== 8. Recycler matching (ranked, authorized-only) ===")
    r = client.get(f"{API}/lots/{lot_id}/matches", headers=auth_header(collector_token))
    check("matches returned", r.status_code == 200 and len(r.json()) > 0, r.text[:300])
    matches = r.json()
    check("matches ranked desc", all(matches[i]["rank_score"] >= matches[i + 1]["rank_score"] for i in range(len(matches) - 1)))
    check("matches include paid price", any(m["offered_price"] for m in matches), str(matches[:1])[:300])
    check("matches include distance", any(m["distance_km"] is not None for m in matches))
    check("only authorized recyclers", all(m["authorization_status"] == "authorized" for m in matches))

    print("\n=== 9. Match lot + digital handover ===")
    r = client.post(
        f"{API}/lots/{lot_id}/match",
        headers=auth_header(collector_token),
        json={"recycler_id": recycler_id},
    )
    check("lot matched", r.status_code == 200 and r.json()["status"] == "matched", r.text[:300])

    r = client.post(
        f"{API}/lots/{lot_id}/handover",
        headers=auth_header(collector_token),
        json={
            "photo_ref": "local://e2e/handover.jpg",
            "latitude": 18.5205,
            "longitude": 73.8568,
            "notes": "Handed to recycler at facility",
        },
    )
    check("handover created", r.status_code == 200 and r.json()["status"] == "handover", r.text[:300])
    handover = r.json()["handover"]
    check("handover has reference number", bool(handover["reference_number"]), str(handover))
    check("handover has GPS", handover["gps_latitude"] is not None)
    check("handover unconfirmed initially", handover["recycler_confirmation"] is False)

    print("\n=== 10. Recycler verifies weight (declared vs verified trust layer) ===")
    r = client.get(f"{API}/recycler/lots", headers=auth_header(recycler_token))
    check("recycler sees incoming lot", r.status_code == 200 and any(l["lot_id"] == lot_id for l in r.json()), r.text[:200])

    r = client.post(
        f"{API}/recycler/lots/{lot_id}/verify",
        headers=auth_header(recycler_token),
        json={"verified_weight": 11.9, "payment_mode": "cash"},
    )
    check("verify weight ok", r.status_code == 200, r.text[:400])
    verified_lot = r.json()
    check("verified weight stored", float(verified_lot["verified_weight"]) == 11.9, str(verified_lot.get("verified_weight")))
    check("declared preserved separately", float(verified_lot["declared_weight"]) == 12.5)
    check("final price on verified weight", float(verified_lot["final_price"]) > 0, str(verified_lot.get("final_price")))
    expected_final = round(float(verified_lot["quoted_price"]) * 11.9, 2)
    check(
        "final price == per-kg rate x verified kg",
        abs(float(verified_lot["final_price"]) - expected_final) < 0.02,
        f"final={verified_lot['final_price']} rate={verified_lot.get('quoted_price')} expected={expected_final}",
    )
    check("handover confirmed", verified_lot["handover"]["recycler_confirmation"] is True)
    check(
        "final price != estimated (uses verified)",
        abs(float(verified_lot["final_price"]) - float(verified_lot["estimated_value"])) > 0.01,
        f"final={verified_lot['final_price']} est={verified_lot['estimated_value']}",
    )
    check("transaction created pending", verified_lot["transaction"]["payment_status"] == "pending", str(verified_lot.get("transaction"))[:200])

    r = client.post(
        f"{API}/recycler/lots/{lot_id}/verify",
        headers=auth_header(recycler_token),
        json={"verified_weight": 11.9},
    )
    check("double verify rejected", r.status_code == 409)

    print("\n=== 11. Payment -> earnings ledger ===")
    r = client.post(
        f"{API}/recycler/lots/{lot_id}/pay?payment_mode=cash", headers=auth_header(recycler_token)
    )
    check("mark paid", r.status_code == 200 and r.json()["status"] == "paid", r.text[:300])

    r = client.get(f"{API}/collectors/me/ledger", headers=auth_header(collector_token))
    ledger = r.json()
    check("ledger total earned > 0", float(ledger["total_earned"]) > 0, str(ledger)[:300])
    check("ledger pending zero after payment", float(ledger["pending_dues"]) == 0)
    check("ledger has transactions", len(ledger["transactions"]) >= 1)
    check("ledger lifetime lots", ledger["lifetime_lots"] >= 1)

    print("\n=== 12. Offline sync (bulk idempotent upload) ===")
    offline_batch = [
        {
            "client_uuid": f"e2e-{rnd}-off-{i}",
            "material_category": cat,
            "declared_weight": 5 + i,
            "district": "Pune",
            "capture_mode": "offline",
            "latitude": 18.51,
            "longitude": 73.85,
        }
        for i, cat in enumerate(["cable", "battery", "motor_magnet"])
    ]
    r = client.post(
        f"{API}/lots/sync", headers=auth_header(collector_token), json=offline_batch
    )
    check("offline sync accepted", r.status_code == 200 and len(r.json()) == 3, r.text[:300])
    check("synced lots valued", all(float(l["estimated_value"]) > 0 for l in r.json()))
    check("synced lots marked offline", all(l["capture_mode"] == "offline" for l in r.json()))

    r = client.post(f"{API}/lots/sync", headers=auth_header(collector_token), json=offline_batch)
    check("offline sync idempotent (no dupes)", len(r.json()) == 3)
    r = client.get(f"{API}/lots", headers=auth_header(collector_token))
    check("no duplicate lots after re-sync", len(r.json()) == 4, f"got {len(r.json())}")

    print("\n=== 13. Admin / Ministry dashboard ===")
    r = client.get(f"{API}/admin/analytics", headers=auth_header(admin_token))
    check("analytics ok", r.status_code == 200, r.text[:300])
    an = r.json()
    check("analytics total lots", an["total_lots"] > 0, str(an["total_lots"]))
    check("analytics critical minerals", len(an["critical_minerals_recovered"]) > 0, str(an["critical_minerals_recovered"])[:200])
    check("analytics CO2 offset", float(an["co2_offset_kg"]) > 0, str(an["co2_offset_kg"]))
    check("analytics district heatmap", len(an["district_heatmap"]) > 0, str(an["district_heatmap"])[:200])
    check("analytics declared vs verified", an["declared_vs_verified"]["verified_lots"] > 0)
    check("analytics carries honesty disclaimer", "not laboratory" in an["is_estimate_disclaimer"].lower())

    r = client.post(
        f"{API}/admin/prices/benchmark",
        headers=auth_header(admin_token),
        json={"material_category": "PCB", "location": "IN", "buying_price": 230.0},
    )
    check("admin sets MSP benchmark", r.status_code == 201 and r.json()["is_benchmark"] is True, r.text[:300])

    r = client.get(f"{API}/admin/fraud-flags", headers=auth_header(admin_token))
    check("fraud flags endpoint", r.status_code == 200)

    r = client.get(f"{API}/admin/audit-log", headers=auth_header(admin_token))
    check("audit log records authorization change", r.status_code == 200 and len(r.json()) > 0, r.text[:200])

    print("\n=== 14. Trend history ===")
    r = client.get(f"{API}/prices/history/PCB")
    check("price history points", r.status_code == 200 and len(r.json()["points"]) > 0, r.text[:200])

    print("\n=== 15. Recycler history ===")
    r = client.get(f"{API}/recycler/history", headers=auth_header(recycler_token))
    check("recycler history", r.status_code == 200 and any(l["lot_id"] == lot_id for l in r.json()), r.text[:200])

    print("\n=== 16. Cleanup (return DB to a demo-clean state) ===")
    try:
        from scripts.purge_e2e import purge

        removed = purge()
        check("e2e artifacts purged", True, str(removed))
        print("  removed:", removed)
    except Exception as exc:  # noqa: BLE001
        check("e2e artifacts purged", False, str(exc))

    print("\n" + "=" * 60)
    print(f"PASSED: {len(PASS)}   FAILED: {len(FAIL)}")
    if FAIL:
        print("\nFailures:")
        for f in FAIL:
            print("  -", f)
    print("=" * 60)
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
