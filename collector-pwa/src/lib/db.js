import Dexie from 'dexie'

/**
 * IndexedDB store for the Collector PWA.
 *
 * This is the real offline persistence layer: lots created without internet,
 * their pending match/handover steps and cached price-board data all live here
 * until background sync succeeds.
 */
export const db = new Dexie('kabadiwala_connect')

db.version(1).stores({
  lots: 'client_uuid, status, sync_state, created_at',
  meta: 'key',
  priceBoard: 'material_category, location',
  recyclers: 'recycler_id, district'
})

export const SYNC_STATE = {
  PENDING: 'pending',
  SYNCED: 'synced',
  ERROR: 'error'
}

export async function putMeta(key, value) {
  await db.meta.put({ key, value, updated_at: new Date().toISOString() })
}

export async function getMeta(key, fallback = null) {
  const row = await db.meta.get(key)
  return row ? row.value : fallback
}

/** Persist a locally-captured lot (works with no network at all). */
export async function saveLocalLot(lot) {
  await db.lots.put({ ...lot, sync_state: lot.sync_state || SYNC_STATE.PENDING })
  return lot
}

export async function listLocalLots() {
  const rows = await db.lots.toArray()
  return rows.sort((a, b) => (b.created_at || '').localeCompare(a.created_at || ''))
}

export async function pendingLots() {
  const rows = await db.lots.where('sync_state').equals(SYNC_STATE.PENDING).toArray()
  return rows.sort((a, b) => (a.created_at || '').localeCompare(b.created_at || ''))
}

export async function markLotSynced(clientUuid, serverPayload) {
  const existing = await db.lots.get(clientUuid)
  if (!existing) return
  await db.lots.put({
    ...existing,
    ...serverPayload,
    client_uuid: clientUuid,
    sync_state: SYNC_STATE.SYNCED,
    synced_at: new Date().toISOString()
  })
}

export async function markLotError(clientUuid, message) {
  const existing = await db.lots.get(clientUuid)
  if (!existing) return
  await db.lots.put({
    ...existing,
    sync_state: SYNC_STATE.ERROR,
    sync_error: message,
    sync_attempts: (existing.sync_attempts || 0) + 1
  })
}

export async function savePriceBoard(entries, location) {
  const now = new Date().toISOString()
  await db.transaction('rw', db.priceBoard, async () => {
    for (const e of entries) {
      await db.priceBoard.put({ ...e, location: location || e.location || 'IN', cached_at: now })
    }
  })
}

export async function readPriceBoard(location) {
  const all = await db.priceBoard.toArray()
  if (!location) return all
  const local = all.filter((e) => e.location === location)
  const national = all.filter((e) => e.location === 'IN')
  return local.length ? local : national
}

export async function saveRecyclers(rows) {
  await db.transaction('rw', db.recyclers, async () => {
    for (const r of rows) {
      await db.recyclers.put({ ...r, cached_at: new Date().toISOString() })
    }
  })
}

export async function readRecyclers() {
  return db.recyclers.toArray()
}

export async function clearAll() {
  await db.transaction('rw', db.lots, db.meta, db.priceBoard, db.recyclers, async () => {
    await Promise.all([
      db.lots.clear(),
      db.meta.clear(),
      db.priceBoard.clear(),
      db.recyclers.clear()
    ])
  })
}
