import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { api } from '../lib/api'
import { fmtInr, fmtKg } from '../lib/constants'
import { useOnline } from '../lib/hooks'

export default function EarningsPage() {
  const { t } = useTranslation()
  const online = useOnline()
  const [ledger, setLedger] = useState(null)
  const [error, setError] = useState(null)

  const load = async () => {
    try {
      setLedger(await api.ledger())
      setError(null)
    } catch (err) {
      setError(online ? err.message : 'Offline — ledger needs a connection to refresh.')
    }
  }

  useEffect(() => {
    load().catch(() => {})
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return (
    <div>
      <header className="app-header">
        <h1>{t('earnings.title')}</h1>
      </header>
      <main className="page">
        {error && <div className="warn-box">{error}</div>}

        <div className="metric-row" style={{ marginBottom: '0.9rem' }}>
          <div className="metric">
            <span className="value">₹{fmtInr(ledger?.total_earned ?? 0)}</span>
            <span className="label">{t('earnings.total')}</span>
          </div>
          <div className="metric">
            <span className="value">₹{fmtInr(ledger?.pending_dues ?? 0)}</span>
            <span className="label">{t('earnings.pending')}</span>
          </div>
          <div className="metric">
            <span className="value">{fmtKg(ledger?.lifetime_kg ?? 0)}</span>
            <span className="label">{t('home.lifetimeKg')}</span>
          </div>
        </div>

        {ledger?.transactions?.length ? (
          ledger.transactions.map((tx) => (
            <div key={tx.transaction_id} className="list-row">
              <span style={{ flex: 1 }}>
                <strong>₹{fmtInr(tx.amount)}</strong>
                <span className="meta" style={{ display: 'block' }}>
                  {tx.payment_mode === 'cash' ? t('earnings.cash') : t('earnings.upi')} ·{' '}
                  {new Date(tx.created_at).toLocaleDateString()}
                </span>
              </span>
              <span className={`badge ${tx.payment_status === 'paid' ? 'synced' : 'pending'}`}>
                {tx.payment_status === 'paid' ? t('earnings.paid') : t('earnings.unpaid')}
              </span>
            </div>
          ))
        ) : (
          <p className="muted">{t('earnings.empty')}</p>
        )}
      </main>
    </div>
  )
}
