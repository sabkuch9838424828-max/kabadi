/**
 * Offline conflict-resolution + sync engine.
 *
 * Rules (documented in README):
 *  - Lots are keyed by a client-generated UUID; the server is idempotent on it,
 *    so re-syncing never creates duplicates.
 *  - Server state wins for anything already settled (verified/paid), because
 *    the recycler's verified weight is the source of truth.
 *  - Locally-created lots that are still pending are pushed in creation order.
 */
import { api } from './api'
import {
  SYNC_STATE,
  markLotError,
  markLotSynced,
  pendingLots
} from './db'

let syncing = false
const listeners = new Set()

export function onSyncEvent(fn) {
  listeners.add(fn)
  return () => listeners.delete(fn)
}

function emit(event) {
  listeners.forEach((fn) => {
    try {
      fn(event)
    } catch {
      /* listener errors must not break sync */
    }
  })
}

export function isSyncing() {
  return syncing
}

function toSyncPayload(lot) {
  return {
    client_uuid: lot.client_uuid,
    material_category: lot.material_category,
    material_sub_category: lot.material_sub_category || null,
    declared_weight: lot.declared_weight,
    image_ref: lot.image_ref || null,
    latitude: lot.latitude ?? null,
    longitude: lot.longitude ?? null,
    district: lot.district || null,
    capture_mode: 'offline',
    created_at_client: lot.created_at || null,
    recycler_id: lot.recycler_id || null,
    handover: lot.handover
      ? {
          photo_ref: lot.handover.photo_ref || null,
          latitude: lot.handover.latitude ?? null,
          longitude: lot.handover.longitude ?? null,
          notes: lot.handover.notes || null,
          captured_at: lot.handover.captured_at || null,
          client_uuid: lot.client_uuid
        }
      : null
  }
}

/** Push all pending offline lots. Returns {synced, failed}. */
export async function syncPendingLots() {
  if (syncing) return { synced: 0, failed: 0, skipped: true }
  if (!navigator.onLine) {
    emit({ type: 'offline' })
    return { synced: 0, failed: 0, skipped: true }
  }

  syncing = true
  emit({ type: 'start' })
  let synced = 0
  let failed = 0

  try {
    const pending = await pendingLots()
    if (!pending.length) {
      emit({ type: 'done', synced: 0, failed: 0 })
      return { synced: 0, failed: 0 }
    }

    const res = await api.syncLots(pending.map(toSyncPayload))
    const byClientUuid = new Map(res.map((r) => [r.client_uuid, r]))

    for (const local of pending) {
      const server = byClientUuid.get(local.client_uuid)
      if (!server) {
        failed += 1
        await markLotError(local.client_uuid, 'Server did not acknowledge this lot')
        continue
      }
      // Conflict rule: settled server state always wins.
      await markLotSynced(local.client_uuid, server)
      synced += 1
      emit({ type: 'item', client_uuid: local.client_uuid, status: 'synced' })
    }
    emit({ type: 'done', synced, failed })
    return { synced, failed }
  } catch (err) {
    emit({ type: 'error', message: err.message })
    // Leave lots pending — they will retry on the next connectivity event.
    return { synced, failed: failed + 1, error: err.message }
  } finally {
    syncing = false
    try {
      await navigator.serviceWorker?.ready
      const sync = window.__kcBgSync
      if (sync) await sync.register('kc-sync-lots').catch(() => {})
    } catch {
      /* Background Sync is best-effort */
    }
  }
}

/** Register the online listener + background sync hook. */
export function installSyncTriggers() {
  window.addEventListener('online', () => {
    syncPendingLots()
  })
  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.ready.then((reg) => {
      window.__kcBgSync = reg.sync
    })
  }
}
