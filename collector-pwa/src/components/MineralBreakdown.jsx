import { useTranslation } from 'react-i18next'

/** Critical-mineral breakdown table — always labelled as an estimate. */
export default function MineralBreakdown({ minerals, co2, disclaimer }) {
  const { t } = useTranslation()
  const rows = Object.values(minerals || {})
  if (!rows.length) return null
  const critical = rows.filter((m) => m.is_critical)

  return (
    <div className="card flat">
      <h3>{t('lot.criticalMinerals')}</h3>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem' }}>
        <tbody>
          {(critical.length ? critical : rows).map((m) => (
            <tr key={m.element} style={{ borderBottom: '1px solid var(--slate-200)' }}>
              <td style={{ padding: '0.35rem 0' }}>
                <strong>{m.element}</strong>
                {m.is_critical && <span className="badge pending" style={{ marginLeft: 6 }}>critical</span>}
              </td>
              <td style={{ textAlign: 'right', padding: '0.35rem 0' }}>
                {Number(m.kg_low).toFixed(3)}–{Number(m.kg_high).toFixed(3)} {t('common.kg')}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {co2 != null && (
        <p style={{ margin: '0.6rem 0 0', fontSize: '0.9rem' }}>
          <strong>{t('lot.co2Offset')}:</strong> {Number(co2).toFixed(2)} kg CO₂e
        </p>
      )}
      <p className="disclaimer">{disclaimer || t('lot.estimateNote')}</p>
    </div>
  )
}
