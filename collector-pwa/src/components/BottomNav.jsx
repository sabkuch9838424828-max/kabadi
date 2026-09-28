import { NavLink } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

const ITEMS = [
  { to: '/', icon: '🏠', key: 'nav.home' },
  { to: '/add', icon: '➕', key: 'nav.addLot' },
  { to: '/prices', icon: '📊', key: 'nav.prices' },
  { to: '/earnings', icon: '💰', key: 'nav.earnings' },
  { to: '/safety', icon: '🦺', key: 'nav.safety' }
]

export default function BottomNav() {
  const { t } = useTranslation()
  return (
    <nav className="bottom-nav" aria-label="Main">
      {ITEMS.map((item) => (
        <NavLink key={item.to} to={item.to} end={item.to === '/'}>
          <span className="icon" aria-hidden="true">
            {item.icon}
          </span>
          <span>{t(item.key)}</span>
        </NavLink>
      ))}
    </nav>
  )
}
