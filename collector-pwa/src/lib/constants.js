export const CATEGORY_EMOJI = {
  PCB: '🟩',
  battery: '🔋',
  motor_magnet: '🧲',
  cable: '🔌',
  CRT: '📺',
  LCD: '🖥️',
  mixed_plastic: '♻️',
  other: '📦'
}

export const CATEGORY_ORDER = [
  'PCB',
  'battery',
  'motor_magnet',
  'cable',
  'CRT',
  'LCD',
  'mixed_plastic',
  'other'
]

export const SAFETY_RULES = [
  { emoji: '🔥', key: 'rule1' },
  { emoji: '🧪', key: 'rule2' },
  { emoji: '🔋', key: 'rule3' },
  { emoji: '📺', key: 'rule4' },
  { emoji: '🧤', key: 'rule5' }
]

export function scoreColor(score) {
  const s = Number(score || 0)
  if (s >= 70) return '#16a34a'
  if (s >= 45) return '#d97706'
  return '#dc2626'
}

export function fmtInr(value) {
  const n = Number(value || 0)
  return n.toLocaleString('en-IN', { maximumFractionDigits: 2 })
}

export function fmtKg(value) {
  const n = Number(value || 0)
  return n.toLocaleString('en-IN', { maximumFractionDigits: 3 })
}
