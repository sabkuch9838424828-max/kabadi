/**
 * Board helpers: the board returns per-location rows; a collector needs the
 * best price for one category and the district-local price when available.
 */
export function boardPriceFor(board, category, district) {
  const rows = (board || []).filter((r) => r.material_category === category)
  if (!rows.length) return null
  if (district) {
    const local = rows.find((r) => r.location === district)
    if (local && Number(local.best_price) > 0) return local
  }
  const national = rows.find((r) => r.location === 'IN' && Number(r.best_price) > 0)
  return national || rows.sort((a, b) => Number(b.best_price) - Number(a.best_price))[0]
}

export function resolveUnitPrice(row) {
  if (!row) return 0
  const best = Number(row.best_price || 0)
  if (best > 0) return best
  const bench = Number(row.benchmark_price || 0)
  return bench > 0 ? bench : 0
}
