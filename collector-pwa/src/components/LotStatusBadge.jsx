import { useTranslation } from 'react-i18next'

export default function LotStatusBadge({ status }) {
  const { t } = useTranslation()
  const labels = {
    created: 'lot.status.created',
    matched: 'lot.status.matched',
    handover: 'lot.status.handover',
    verified: 'lot.status.verified',
    paid: 'lot.status.paid',
    declined: 'lot.status.declined'
  }
  return <span className={`badge status`}>{t(labels[status] || status)}</span>
}
