/**
 * Client-side recycler matching (offline mirror of the server ranking).
 *
 * Uses the cached recycler directory + cached price board, so a collector can
 * still pick an authorized recycler and record a handover with no network.
 * On sync the server re-ranks authoritatively.
 */
function haversineKm(aLat, aLon, bLat, bLon) {
  const R = 6371
  const toRad = (d) => (d * Math.PI) / 180
  const dLat = toRad(bLat - aLat)
  const dLon = toRad(bLon - aLon)
  const h =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(toRad(aLat)) * Math.cos(toRad(bLat)) * Math.sin(dLon / 2) ** 2
  return 2 * R * Math.asin(Math.sqrt(h))
}

export function matchRecyclersOffline({ recyclers, board, category, weightKg, lat, lon }) {
  const priceByCategoryLocation = new Map()
  for (const e of board || []) {
    const key = `${e.material_category}|${e.location}`
    const existing = priceByCategoryLocation.get(key)
    const price = Number(e.best_price || 0)
    if (!existing || price > existing) priceByCategoryLocation.set(key, price)
  }

  const results = []
  for (const r of recyclers || []) {
    if (r.authorization_status !== 'authorized') continue
    if (Array.isArray(r.materials_accepted) && r.materials_accepted.length && !r.materials_accepted.includes(category)) {
      continue
    }
    const offeredNational = priceByCategoryLocation.get(`${category}|IN`) || 0
    const offeredLocal = r.district ? priceByCategoryLocation.get(`${category}|${r.district}`) || 0 : 0
    const offered = offeredLocal || offeredNational

    let distance = null
    if (lat != null && lon != null && r.latitude != null && r.longitude != null) {
      distance = haversineKm(lat, lon, r.latitude, r.longitude)
    }

    const reasons = []
    let score = 0
    if (offered) {
      const priceScore = Math.min(offered / 400, 1) * 45
      score += priceScore
      reasons.push(`Offers ₹${offered.toFixed(0)}/kg`)
    }
    if (distance != null) {
      const distScore = Math.max(0, 1 - distance / 100) * 35
      score += distScore
      reasons.push(`${distance.toFixed(1)} km away`)
    } else {
      score += 15
      reasons.push('Location unknown')
    }
    if (r.pickup_available) {
      score += 10
      reasons.push('Pickup available')
    }
    const cap = Number(r.capacity_kg_per_day || 0)
    if (cap && weightKg && cap >= weightKg) {
      score += 10
      reasons.push(`Capacity ${cap} kg/day`)
    }
    if (r.district) {
      score += 5
      reasons.push(`Operates in ${r.district}`)
    }

    results.push({
      recycler_id: r.recycler_id,
      name: r.name,
      district: r.district,
      state: r.state,
      materials_accepted: r.materials_accepted || [],
      authorization_status: r.authorization_status,
      pickup_available: r.pickup_available,
      capacity_kg_per_day: r.capacity_kg_per_day,
      latitude: r.latitude,
      longitude: r.longitude,
      distance_km: distance,
      offered_price: offered || null,
      rank_score: +score.toFixed(2),
      rank_reasons: reasons,
      offline_ranking: true
    })
  }

  return results.sort((a, b) => b.rank_score - a.rank_score)
}
