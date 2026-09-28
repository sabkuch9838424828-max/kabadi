import { useTranslation } from 'react-i18next'
import { scoreColor } from '../lib/constants'

/** Recovery Score ring (0-100) with the honesty label. */
export default function RecoveryScore({ score, size = 92 }) {
  const { t } = useTranslation()
  const value = Number(score || 0)
  const color = scoreColor(value)
  return (
    <div className="score-ring">
      <div
        className="score-circle"
        style={{
          background: `conic-gradient(${color} ${value * 3.6}deg, #e2e8f0 0deg)`,
          width: size,
          height: size
        }}
        role="img"
        aria-label={`${t('lot.recoveryScore')}: ${value} / 100`}
      >
        <div
          style={{
            background: '#fff',
            color,
            borderRadius: '50%',
            width: size - 16,
            height: size - 16,
            display: 'grid',
            placeItems: 'center',
            fontSize: '1.35rem',
            fontWeight: 800
          }}
        >
          {Math.round(value)}
          <small style={{ fontSize: '0.55rem', color: '#64748b' }}>/ 100</small>
        </div>
      </div>
      <div>
        <h3 style={{ margin: 0 }}>{t('lot.recoveryScore')}</h3>
        <p className="muted" style={{ margin: '0.2rem 0 0' }}>
          {t('lot.recoveryScoreHelp')}
        </p>
      </div>
    </div>
  )
}
