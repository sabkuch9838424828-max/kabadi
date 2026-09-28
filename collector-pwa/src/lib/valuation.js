/**
 * Client-side mirror of the server stoichiometric engine.
 *
 * Uses the configuration fetched from /ml/valuation-config (published
 * composition ratios + scoring weights) so that a lot created with no network
 * still receives a real estimated value and Recovery Score. The server
 * recalculates on sync, so the offline number is provisional and labelled as
 * an estimate — never presented as an assay.
 */
const D = (v) => Number(v)

export function computeValuation(config, category, weightKg, unitPrice) {
  if (!config || !config.compositions) {
    return {
      estimated_value: 0,
      recovery_score: 0,
      co2_offset_kg: 0,
      minerals: [],
      is_estimate: true,
      disclaimer: 'Valuation unavailable offline (configuration not cached yet).'
    }
  }

  const rows = config.compositions[category] || []
  const elementValues = config.element_values_inr_per_kg || {}
  const criticalSet = new Set(config.critical_elements || [])
  const w = config.score_weights || {}

  const minerals = rows.map((r) => {
    const mid = D(r.ratio_mid) * weightKg
    return {
      element: r.element,
      kg_low: +(D(r.ratio_low) * weightKg).toFixed(3),
      kg_mid: +mid.toFixed(3),
      kg_high: +(D(r.ratio_high) * weightKg).toFixed(3),
      is_critical: r.is_critical || criticalSet.has(r.element),
      value_inr: +(mid * D(elementValues[r.element] || 0)).toFixed(2)
    }
  })

  const co2Factor = rows.length ? D(rows[0].co2_factor) : 0
  const co2Offset = +(co2Factor * weightKg).toFixed(3)
  const estimatedValue = +(D(unitPrice || 0) * weightKg).toFixed(2)

  const criticalKg = minerals
    .filter((m) => criticalSet.has(m.element))
    .reduce((sum, m) => sum + m.kg_mid, 0)

  const mineralFraction = weightKg > 0 ? criticalKg / weightKg : 0
  const mineralFullMark = D(w.mineral_full_mark_fraction || 0.25)
  const co2FullMark = D(w.co2_full_mark_per_kg || 8)
  const co2PerKg = weightKg > 0 ? co2Offset / weightKg : 0

  const score =
    Math.min(mineralFraction / mineralFullMark, 1) * D(w.minerals || 55) +
    Math.min(co2PerKg / co2FullMark, 1) * D(w.co2 || 30) +
    D((config.recyclability || {})[category] || 0.45) * D(w.recyclability || 15)

  return {
    estimated_value: estimatedValue,
    recovery_score: +Math.min(score, 100).toFixed(2),
    co2_offset_kg: co2Offset,
    minerals,
    is_estimate: true,
    basis: 'offline_published_stoichiometric_ratios',
    disclaimer: config.disclaimer
  }
}
