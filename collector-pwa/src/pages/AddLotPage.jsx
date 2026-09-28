import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { api } from '../lib/api'
import { getMeta, putMeta, saveLocalLot, SYNC_STATE } from '../lib/db'
import { computeValuation } from '../lib/valuation'
import { boardPriceFor, resolveUnitPrice } from '../lib/board'
import { CATEGORY_ORDER, fmtInr, fmtKg } from '../lib/constants'
import CategoryChip from '../components/CategoryChip'
import RecoveryScore from '../components/RecoveryScore'
import MineralBreakdown from '../components/MineralBreakdown'
import { useOnline } from '../lib/hooks'
import { useSession, useSyncState } from '../state'
import { syncPendingLots } from '../lib/sync'

function uuid() {
  if (crypto.randomUUID) return crypto.randomUUID()
  return `kc-${Date.now()}-${Math.random().toString(16).slice(2)}`
}

export default function AddLotPage() {
  const { t } = useTranslation()
  const nav = useNavigate()
  const online = useOnline()
  const { profile } = useSession()
  const { refreshPending } = useSyncState()

  const fileRef = useRef(null)
  const [photo, setPhoto] = useState(null)
  const [photoDataUrl, setPhotoDataUrl] = useState(null)
  const [classifying, setClassifying] = useState(false)
  const [aiResult, setAiResult] = useState(null)
  const [category, setCategory] = useState(null)
  const [weight, setWeight] = useState('')
  const [valuation, setValuation] = useState(null)
  const [config, setConfig] = useState(null)
  const [board, setBoard] = useState([])
  const [error, setError] = useState(null)
  const [saving, setSaving] = useState(false)
  const [savedMsg, setSavedMsg] = useState(null)
  const [location, setLocation] = useState(null)

  const district = profile?.collector?.district || null

  useEffect(() => {
    Promise.all([loadConfig(), loadBoard()])
      .then(([cfg, b]) => recompute(category, weight, cfg, b))
      .catch(() => {})
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const captureLocation = () =>
    new Promise((resolve) => {
      if (location) return resolve(location)
      if (!navigator.geolocation) return resolve(null)
      navigator.geolocation.getCurrentPosition(
        (pos) => {
          const loc = { latitude: pos.coords.latitude, longitude: pos.coords.longitude }
          setLocation(loc)
          resolve(loc)
        },
        () => resolve(null),
        { timeout: 8000 }
      )
    })

  const loadConfig = async () => {
    if (config) return config
    try {
      const cfg = await api.valuationConfig()
      setConfig(cfg)
      await putMeta('valuation_config', cfg)
      return cfg
    } catch {
      const cached = await getMeta('valuation_config')
      if (cached) setConfig(cached)
      return cached
    }
  }

  const loadBoard = async () => {
    try {
      const b = await api.priceBoard(district || undefined)
      setBoard(b)
      await putMeta('price_board', b)
      return b
    } catch {
      const cached = (await getMeta('price_board')) || []
      setBoard(cached)
      return cached
    }
  }

  const onPhoto = async (event) => {
    const file = event.target.files?.[0]
    if (!file) return
    setError(null)
    setAiResult(null)
    setPhoto(file)
    const reader = new FileReader()
    reader.onload = () => setPhotoDataUrl(reader.result)
    reader.readAsDataURL(file)
    window.__kcPendingPhoto = file

    setClassifying(true)
    try {
      const [cfg, b] = await Promise.all([loadConfig(), loadBoard()])
      let result = null
      if (online) {
        try {
          result = await api.classify(file)
        } catch (err) {
          setError(`AI classification unavailable: ${err.message}. Please pick the material manually.`)
        }
      } else {
        setError('You are offline — please pick the material manually. It still works.')
      }
      if (result) {
        setAiResult(result)
        setCategory(result.material_category)
        recompute(result.material_category, weight, cfg, b)
      }
    } finally {
      setClassifying(false)
    }
  }

  const recompute = (cat, w, cfg = config, b = board) => {
    const weightNum = parseFloat(w)
    if (!cat || !weightNum || weightNum <= 0) {
      setValuation(null)
      return
    }
    const price = resolveUnitPrice(boardPriceFor(b, cat, district))
    const local = computeValuation(cfg, cat, weightNum, price)
    local.price_source = price > 0 ? 'board' : 'unavailable'
    local.unit_price = price
    setValuation(local)
  }

  const onCategory = (cat) => {
    setCategory(cat)
    recompute(cat, weight)
  }

  const onWeight = (value) => {
    setWeight(value)
    recompute(category, value)
  }

  const save = async () => {
    if (!category) {
      setError('Please choose the material type.')
      return
    }
    const weightNum = parseFloat(weight)
    if (!weightNum || weightNum <= 0) {
      setError('Please enter the approximate weight in kg.')
      return
    }
    setSaving(true)
    setError(null)
    try {
      const loc = await captureLocation()
      const clientUuid = uuid()
      const localLot = {
        client_uuid: clientUuid,
        material_category: category,
        declared_weight: weightNum,
        image_ref: photo ? `local://${photo.name}` : null,
        latitude: loc?.latitude ?? profile?.collector?.latitude ?? null,
        longitude: loc?.longitude ?? profile?.collector?.longitude ?? null,
        district,
        capture_mode: online ? 'online' : 'offline',
        created_at: new Date().toISOString(),
        status: 'created',
        sync_state: SYNC_STATE.PENDING,
        estimated_value: valuation?.estimated_value ?? 0,
        recovery_score: valuation?.recovery_score ?? null,
        mineral_estimate: valuation
          ? {
              minerals: Object.fromEntries((valuation.minerals || []).map((m) => [m.element, m])),
              co2_offset_kg: valuation.co2_offset_kg,
              is_estimate: true,
              disclaimer: valuation.disclaimer
            }
          : null,
        provisional: true
      }

      // Always persist locally first — this is what makes the app work offline.
      await saveLocalLot(localLot)
      await refreshPending()
      setSavedMsg(online ? t('lot.saved') : t('lot.savedOffline'))

      if (online) {
        syncPendingLots().catch(() => {})
      }

      setTimeout(() => nav(`/lots/${clientUuid}`), 600)
    } catch (err) {
      setError(err.message)
    } finally {
      setSaving(false)
    }
  }

  const unitPrice = valuation?.unit_price

  return (
    <div>
      <header className="app-header">
        <h1>{t('lot.title')}</h1>
        {!online && <span className="badge offline">{t('offline.title')}</span>}
      </header>

      <main className="page">
        {error && <div className="error-box">{error}</div>}
        {savedMsg && <div className="info-box">✅ {savedMsg}</div>}

        <div className="card">
          <h3>{t('lot.step.photo')}</h3>
          {photoDataUrl ? (
            <img src={photoDataUrl} alt="" className="photo-preview" />
          ) : (
            <button className="btn-secondary" onClick={() => fileRef.current?.click()}>
              📷 {t('lot.takePhoto')}
            </button>
          )}
          <input
            ref={fileRef}
            type="file"
            accept="image/*"
            capture="environment"
            onChange={onPhoto}
            style={{ display: 'none' }}
          />
          {photoDataUrl && (
            <button className="btn-ghost" style={{ width: '100%', marginTop: '0.5rem' }} onClick={() => fileRef.current?.click()}>
              {t('lot.choosePhoto')}
            </button>
          )}
          {classifying && (
            <p className="muted">
              <span className="spinner" /> {t('lot.analysing')}
            </p>
          )}
          {aiResult && (
            <div className="info-box" style={{ marginTop: '0.6rem' }}>
              🤖 {t('lot.aiSuggestion', {
                category: t(`category.${aiResult.material_category}`),
                confidence: Math.round(aiResult.confidence * 100)
              })}
              <div className="disclaimer">{aiResult.disclaimer || t('lot.aiDisclaimer')}</div>
            </div>
          )}
        </div>

        <div className="card">
          <h3>{t('lot.step.category')}</h3>
          <div className="chip-grid">
            {CATEGORY_ORDER.map((c) => (
              <CategoryChip
                key={c}
                category={c}
                selected={category === c}
                onClick={() => onCategory(c)}
                confidence={aiResult?.material_category === c ? aiResult.confidence : null}
              />
            ))}
          </div>
        </div>

        <div className="card">
          <h3>{t('lot.step.weight')}</h3>
          <div className="field">
            <input
              type="number"
              inputMode="decimal"
              min="0.1"
              step="0.1"
              placeholder="0.0"
              value={weight}
              onChange={(e) => onWeight(e.target.value)}
            />
            <p className="muted" style={{ marginTop: '0.3rem' }}>
              {t('lot.weightHint')}
            </p>
          </div>

          <div className="metric-row">
            <div className="metric">
              <span className="value">₹{fmtInr(valuation?.estimated_value ?? 0)}</span>
              <span className="label">{t('lot.value')}</span>
            </div>
            <div className="metric">
              <span className="value">{fmtKg(weight || 0)}</span>
              <span className="label">{t('common.kg')}</span>
            </div>
            <div className="metric">
              <span className="value">{unitPrice != null ? `₹${fmtInr(unitPrice)}` : '—'}</span>
              <span className="label">/ {t('common.kg')}</span>
            </div>
          </div>
        </div>

        {valuation && (
          <>
            <div className="card">
              <RecoveryScore score={valuation.recovery_score} />
            </div>
            <MineralBreakdown
              minerals={Object.fromEntries((valuation.minerals || []).map((m) => [m.element, m]))}
              co2={valuation.co2_offset_kg}
              disclaimer={valuation.disclaimer}
            />
          </>
        )}

        <button className="btn-primary" onClick={save} disabled={saving || !category || !weight}>
          {saving ? <span className="spinner" /> : `💾 ${t('lot.saveOffline')}`}
        </button>
        <p className="muted" style={{ textAlign: 'center' }}>
          {online ? t('offline.off') : t('offline.on')}
        </p>
      </main>
    </div>
  )
}
