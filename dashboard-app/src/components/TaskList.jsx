import React, { useState } from 'react'
import { ChevronDown, ChevronRight, AlertTriangle, CalendarClock, Calendar, Inbox } from 'lucide-react'
import TaskCard from './TaskCard'
import { groupTasks } from '../utils/dateUtils'

function Section({ title, icon: Icon, count, color, defaultOpen = false, children }) {
  const [open, setOpen] = useState(defaultOpen)

  if (count === 0) return null

  return (
    <div className="mb-3">
      <button
        onClick={() => setOpen(!open)}
        className={`w-full flex items-center justify-between px-3 py-2 rounded-lg ${color}`}
      >
        <div className="flex items-center gap-2">
          {open ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
          <Icon size={16} />
          <span className="text-sm font-semibold">{title}</span>
        </div>
        <span className="text-xs font-bold bg-white/60 px-2 py-0.5 rounded-full">{count}</span>
      </button>
      {open && <div className="mt-2 space-y-2">{children}</div>}
    </div>
  )
}

export default function TaskList({ tasks, onSelectTask, isLoading }) {
  if (isLoading) {
    return (
      <div className="space-y-3 p-4">
        {[1, 2, 3, 4].map(i => (
          <div key={i} className="bg-white rounded-lg h-20 animate-pulse border border-gray-100" />
        ))}
      </div>
    )
  }

  if (!tasks || tasks.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-16 px-4 text-center">
        <Inbox size={48} className="text-gray-300 mb-3" />
        <h3 className="text-lg font-semibold text-gray-600">No active tasks</h3>
        <p className="text-sm text-gray-400 mt-1">All caught up! Tasks assigned to you will appear here.</p>
      </div>
    )
  }

  // Filter out subtasks (they show inside parent task detail)
  const parentTasks = tasks.filter(t => !t.parent_task)
  const groups = groupTasks(parentTasks)

  return (
    <div className="p-4 space-y-1">
      <Section
        title="Overdue"
        icon={AlertTriangle}
        count={groups.overdue.length}
        color="bg-red-50 text-red-700"
        defaultOpen={true}
      >
        {groups.overdue.map(task => (
          <TaskCard key={task.name} task={task} onSelect={onSelectTask} />
        ))}
      </Section>

      <Section
        title="Due Today"
        icon={CalendarClock}
        count={groups.today.length}
        color="bg-amber-50 text-amber-700"
        defaultOpen={true}
      >
        {groups.today.map(task => (
          <TaskCard key={task.name} task={task} onSelect={onSelectTask} />
        ))}
      </Section>

      <Section
        title="Due This Week"
        icon={Calendar}
        count={groups.thisWeek.length}
        color="bg-blue-50 text-blue-700"
        defaultOpen={true}
      >
        {groups.thisWeek.map(task => (
          <TaskCard key={task.name} task={task} onSelect={onSelectTask} />
        ))}
      </Section>

      <Section
        title="Open"
        icon={Inbox}
        count={groups.open.length}
        color="bg-gray-100 text-gray-700"
        defaultOpen={groups.overdue.length === 0 && groups.today.length === 0}
      >
        {groups.open.map(task => (
          <TaskCard key={task.name} task={task} onSelect={onSelectTask} />
        ))}
      </Section>
    </div>
  )
}
