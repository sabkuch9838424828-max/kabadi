import { useTranslation } from 'react-i18next'
import { CATEGORY_EMOJI } from '../lib/constants'

export default function CategoryChip({ category, selected, onClick, confidence }) {
  const { t } = useTranslation()
  return (
    <button
      type="button"
      className={`chip ${selected ? 'selected' : ''}`}
      onClick={onClick}
      aria-pressed={selected}
    >
      <span className="emoji" aria-hidden="true">
        {CATEGORY_EMOJI[category] || '📦'}
      </span>
      <span>
        {t(`category.${category}`)}
        {confidence != null && <strong> · {Math.round(confidence * 100)}%</strong>}
      </span>
    </button>
  )
}
