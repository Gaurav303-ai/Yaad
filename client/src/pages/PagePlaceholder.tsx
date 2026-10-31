// TODO: Replace this shared shell with page-specific layouts as features are built.
import type { JSX } from 'react'

interface PagePlaceholderProps {
  title: string
}

export function PagePlaceholder({ title }: PagePlaceholderProps): JSX.Element {
  return (
    <section>
      <h1 className="page-title">{title}</h1>
      <p className="coming-soon">Coming soon</p>
    </section>
  )
}
