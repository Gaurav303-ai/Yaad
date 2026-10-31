// TODO: Expand the application navigation when feature flows are added.
import type { JSX } from 'react'
import { NavLink } from 'react-router-dom'

const navigation = [
  { label: 'Dashboard', to: '/' },
  { label: 'Meetings', to: '/meetings' },
  { label: 'Conflicts', to: '/conflicts' },
  { label: 'Memory', to: '/memory' },
  { label: 'People', to: '/people' },
  { label: 'Digest', to: '/digest' },
]

export function Sidebar(): JSX.Element {
  return (
    <aside className="sidebar">
      <div className="brand">Yaad</div>
      <nav aria-label="Main navigation" className="nav-links">
        {navigation.map(({ label, to }) => (
          <NavLink
            className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}
            end={to === '/'}
            key={to}
            to={to}
          >
            {label}
          </NavLink>
        ))}
      </nav>
    </aside>
  )
}
