export function formatDate(unix) {
  const n = Number(unix)
  if (!n) return '—'
  const d = new Date(n * 1000)
  if (Number.isNaN(d.getTime())) return '—'
  const months = [
    'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
    'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec',
  ]
  const day = String(d.getDate()).padStart(2, '0')
  return `${months[d.getMonth()]} ${day}, ${d.getFullYear()}`
}
