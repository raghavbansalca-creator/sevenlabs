export const STATUS_CONFIG = {
  Open: { bg: 'bg-blue-50', text: 'text-blue-700', border: 'border-blue-400', label: 'Open' },
  Working: { bg: 'bg-yellow-50', text: 'text-yellow-700', border: 'border-yellow-400', label: 'Working' },
  'Pending Review': { bg: 'bg-purple-50', text: 'text-purple-700', border: 'border-purple-400', label: 'Pending Review' },
  Completed: { bg: 'bg-green-50', text: 'text-green-700', border: 'border-green-400', label: 'Completed' },
  Cancelled: { bg: 'bg-gray-50', text: 'text-gray-500', border: 'border-gray-300', label: 'Cancelled' },
  Overdue: { bg: 'bg-red-50', text: 'text-red-700', border: 'border-red-400', label: 'Overdue' },
}

export const PRIORITY_CONFIG = {
  Low: { bg: 'bg-green-50', text: 'text-green-700', dot: 'bg-green-500' },
  Medium: { bg: 'bg-yellow-50', text: 'text-yellow-700', dot: 'bg-yellow-500' },
  High: { bg: 'bg-orange-50', text: 'text-orange-700', dot: 'bg-orange-500' },
  Urgent: { bg: 'bg-red-50', text: 'text-red-700', dot: 'bg-red-500' },
}

export const STATUSES = ['Open', 'Working', 'Pending Review', 'Overdue', 'Completed', 'Cancelled']
export const ACTIVE_STATUSES = ['Open', 'Working', 'Pending Review', 'Overdue']
export const PRIORITIES = ['Low', 'Medium', 'High', 'Urgent']

export const TASK_FIELDS = [
  'name', 'subject', 'status', 'priority', 'project',
  'exp_start_date', 'exp_end_date', '_assign', 'is_group',
  'parent_task', 'progress', 'custom_task_list', 'modified',
  'creation', 'owner', 'description',
]
