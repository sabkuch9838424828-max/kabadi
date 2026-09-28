import { useTranslation } from 'react-i18next'
import { SAFETY_RULES } from '../lib/constants'
import { speak, speechSupported, stopSpeaking } from '../lib/speech'

export default function SafetyPage() {
  const { t, i18n } = useTranslation()

  return (
    <div>
      <header className="app-header">
        <div>
          <h1>{t('safety.title')}</h1>
          <div className="sub">{t('safety.subtitle')}</div>
        </div>
      </header>
      <main className="page">
        {SAFETY_RULES.map((rule) => {
          const title = t(`safety.${rule.key}.title`)
          const body = t(`safety.${rule.key}.body`)
          return (
            <div key={rule.key} className="card">
              <div className="safety-item">
                <span className="emoji" aria-hidden="true">
                  {rule.emoji}
                </span>
                <div style={{ flex: 1 }}>
                  <h3>{title}</h3>
                  <p style={{ margin: 0 }}>{body}</p>
                  {speechSupported() && (
                    <button
                      className="btn-ghost"
                      style={{ marginTop: '0.4rem' }}
                      onClick={() => {
                        stopSpeaking()
                        speak(`${title}. ${body}`, i18n.language)
                      }}
                    >
                      🔊 {t('safety.listen')}
                    </button>
                  )}
                </div>
              </div>
            </div>
          )
        })}
        <p className="disclaimer">
          Aligned with the E-Waste (Management) Rules, 2022 — safe handling duties for informal
          collectors.
        </p>
      </main>
    </div>
  )
}
