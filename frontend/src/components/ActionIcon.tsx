import type { Action } from '../types'

// One glyph per action on a 24 grid, drawn with currentColor:
// a drop (water), a rain cloud (rain does the watering), a clock (not yet), the sun (heat).
export default function ActionIcon({ action, size = 22 }: { action: Action; size?: number }) {
  const common = {
    width: size,
    height: size,
    viewBox: '0 0 24 24',
    fill: 'none',
    stroke: 'currentColor',
    strokeWidth: 2,
    strokeLinecap: 'round' as const,
    strokeLinejoin: 'round' as const,
    'aria-hidden': true,
    focusable: false,
  }
  switch (action) {
    case 'IRRIGATE':
      return (
        <svg {...common}>
          <path d="M12 2.8s-6.4 7.4-6.4 11.4a6.4 6.4 0 0 0 12.8 0c0-4-6.4-11.4-6.4-11.4z" fill="currentColor" stroke="none" />
        </svg>
      )
    case 'SKIP':
      return (
        <svg {...common}>
          <path d="M7 15.5a4 4 0 0 1-.6-8 5.5 5.5 0 0 1 10.6 1.3A3.4 3.4 0 0 1 17 15.5z" />
          <path d="M8 18.5l-1 2.5M12.5 18.5l-1 2.5M17 18.5l-1 2.5" />
        </svg>
      )
    case 'WAIT':
      return (
        <svg {...common}>
          <circle cx="12" cy="12" r="8.5" />
          <path d="M12 7.5V12l3 2" />
        </svg>
      )
    case 'HEAT_PROTECTION':
      return (
        <svg {...common}>
          <circle cx="12" cy="12" r="4.2" fill="currentColor" stroke="none" />
          <path d="M12 2.5v2.6M12 18.9v2.6M2.5 12h2.6M18.9 12h2.6M5.3 5.3l1.8 1.8M16.9 16.9l1.8 1.8M5.3 18.7l1.8-1.8M16.9 7.1l1.8-1.8" />
        </svg>
      )
  }
}
