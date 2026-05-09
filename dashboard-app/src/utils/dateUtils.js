/**
 * ERPNext returns dates as "2026-02-15 00:00:00"
 * HTML date inputs need "YYYY-MM-DD"
 * Strip time component per Frappe learning
 */
export function stripTime(dateStr) {
  if (!dateStr) return ''
  return dateStr.split(' ')[0]
}

export function isOverdue(dateStr) {
  if (!dateStr) return false
  const d = stripTime(dateStr)
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  return new Date(d) < today
}

export function isToday(dateStr) {
  if (!dateStr) return false
  const d = stripTime(dateStr)
  const today = new Date()
  return d === today.toISOString().split('T')[0]
}

export function isThisWeek(dateStr) {
  if (!dateStr) return false
  const d = new Date(stripTime(dateStr))
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  const weekEnd = new Date(today)
  weekEnd.setDate(weekEnd.getDate() + 7)
  return d >= today && d <= weekEnd
}

export function formatDate(dateStr) {
  if (!dateStr) return ''
  const d = new Date(stripTime(dateStr))
  return d.toLocaleDateString('en-IN', { day: 'numeric', month: 'short' })
}

export function formatDateFull(dateStr) {
  if (!dateStr) return ''
  const d = new Date(stripTime(dateStr))
  return d.toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })
}

export function daysOverdue(dateStr) {
  if (!dateStr) return 0
  const d = new Date(stripTime(dateStr))
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  const diff = Math.floor((today - d) / (1000 * 60 * 60 * 24))
  return diff > 0 ? diff : 0
}

export function timeAgo(dateStr) {
  if (!dateStr) return ''
  const d = new Date(dateStr)
  const now = new Date()
  const diffMs = now - d
  const diffMins = Math.floor(diffMs / 60000)
  if (diffMins < 1) return 'just now'
  if (diffMins < 60) return `${diffMins}m ago`
  const diffHrs = Math.floor(diffMins / 60)
  if (diffHrs < 24) return `${diffHrs}h ago`
  const diffDays = Math.floor(diffHrs / 24)
  if (diffDays < 7) return `${diffDays}d ago`
  return formatDate(dateStr)
}

/**
 * Group tasks into urgency buckets
 */
export function groupTasks(tasks) {
  const overdue = []
  const today = []
  const thisWeek = []
  const open = []

  tasks.forEach(task => {
    const endDate = task.exp_end_date
    if (isOverdue(endDate) && task.status !== 'Completed' && task.status !== 'Cancelled') {
      overdue.push(task)
    } else if (isToday(endDate)) {
      today.push(task)
    } else if (isThisWeek(endDate)) {
      thisWeek.push(task)
    } else {
      open.push(task)
    }
  })

  // Sort overdue by most overdue first
  overdue.sort((a, b) => new Date(stripTime(a.exp_end_date)) - new Date(stripTime(b.exp_end_date)))

  return { overdue, today, thisWeek, open }
}

/**
 * Parse _assign JSON field
 */
export function parseAssign(assignStr) {
  if (!assignStr) return []
  try {
    const parsed = JSON.parse(assignStr)
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return []
  }
}

/**
 * Get initials from email or name
 */
export function getInitials(str) {
  if (!str) return '?'
  // If it's an email, take first letter of local part
  if (str.includes('@')) {
    return str.split('@')[0].charAt(0).toUpperCase()
  }
  // If it's a name, take first letters of first two words
  const parts = str.split(' ')
  if (parts.length >= 2) {
    return (parts[0].charAt(0) + parts[1].charAt(0)).toUpperCase()
  }
  return str.charAt(0).toUpperCase()
}
