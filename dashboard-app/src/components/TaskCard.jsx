import React from 'react'
import { Clock, AlertCircle } from 'lucide-react'
import { STATUS_CONFIG, PRIORITY_CONFIG } from '../utils/constants'
import { formatDate, isOverdue, daysOverdue, parseAssign, getInitials } from '../utils/dateUtils'

export default React.memo(function TaskCard({ task, onSelect }) {
  const status = STATUS_CONFIG[task.status] || STATUS_CONFIG.Open
  const priority = PRIORITY_CONFIG[task.priority] || PRIORITY_CONFIG.Medium
  const assignees = parseAssign(task._assign)
  const overdue = isOverdue(task.exp_end_date) && task.status !== 'Completed' && task.status !== 'Cancelled'
  const days = daysOverdue(task.exp_end_date)

  return (
    <div
      onClick={() => onSelect(task)}
      className={`bg-white rounded-lg border-l-4 ${overdue ? 'border-l-red-500' : status.border.replace('border-', 'border-l-')} shadow-sm p-3 active:bg-gray-50 cursor-pointer`}
      style={{ minHeight: '72px' }}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1 min-w-0">
          <h3 className="text-sm font-semibold text-gray-900 truncate">{task.subject}</h3>
          {task.project && (
            <p className="text-xs text-gray-500 mt-0.5 truncate">{task.project}</p>
          )}
        </div>
        <span className={`shrink-0 inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${priority.bg} ${priority.text}`}>
          <span className={`w-1.5 h-1.5 rounded-full ${priority.dot}`} />
          {task.priority}
        </span>
      </div>

      <div className="flex items-center justify-between mt-2">
        <div className="flex items-center gap-2">
          <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${status.bg} ${status.text}`}>
            {status.label}
          </span>
          {task.exp_end_date && (
            <span className={`inline-flex items-center gap-1 text-xs ${overdue ? 'text-red-600 font-semibold' : 'text-gray-500'}`}>
              {overdue ? <AlertCircle size={12} /> : <Clock size={12} />}
              {overdue ? `${days}d overdue` : formatDate(task.exp_end_date)}
            </span>
          )}
        </div>

        <div className="flex -space-x-1.5">
          {assignees.slice(0, 3).map((email) => (
            <div
              key={email}
              className="w-6 h-6 rounded-full bg-frappe-blue text-white flex items-center justify-center text-xs font-medium ring-2 ring-white"
              title={email}
            >
              {getInitials(email)}
            </div>
          ))}
          {assignees.length > 3 && (
            <div className="w-6 h-6 rounded-full bg-gray-200 text-gray-600 flex items-center justify-center text-xs font-medium ring-2 ring-white">
              +{assignees.length - 3}
            </div>
          )}
        </div>
      </div>

      {task.progress > 0 && (
        <div className="mt-2">
          <div className="w-full bg-gray-100 rounded-full h-1.5">
            <div
              className={`h-1.5 rounded-full ${task.progress >= 100 ? 'bg-green-500' : 'bg-frappe-blue'}`}
              style={{ width: `${Math.min(task.progress, 100)}%` }}
            />
          </div>
        </div>
      )}
    </div>
  )
})
