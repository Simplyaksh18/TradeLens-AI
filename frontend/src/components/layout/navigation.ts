import {
  LineChart,
  Database,
  FlaskConical,
  History,
  ShieldCheck,
  Microscope,
  Compass,
  Settings as SettingsIcon,
  BookText,
  type LucideIcon,
} from 'lucide-react'

export interface NavItem {
  label: string
  path: string
  icon: LucideIcon
}

export interface NavGroup {
  label: string
  items: NavItem[]
}

export const NAV_GROUPS: NavGroup[] = [
  {
    label: 'Research',
    items: [
      { label: 'Overview', path: '/', icon: LineChart },
      { label: 'Data Explorer', path: '/data-explorer', icon: Database },
      { label: 'Strategy Lab', path: '/strategy-lab', icon: FlaskConical },
    ],
  },
  {
    label: 'Validation',
    items: [
      { label: 'Backtests', path: '/backtests', icon: History },
      { label: 'Strategy Auditor', path: '/trade-auditor', icon: ShieldCheck },
      { label: 'Failure Investigator', path: '/failure-investigator', icon: Microscope },
    ],
  },
  {
    label: 'Intelligence',
    items: [{ label: 'Research Workspace', path: '/research', icon: Compass }],
  },
  {
    label: 'System',
    items: [
      { label: 'Settings', path: '/settings', icon: SettingsIcon },
      { label: 'Documentation', path: '/docs', icon: BookText },
    ],
  },
]
