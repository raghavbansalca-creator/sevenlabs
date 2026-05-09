import React, { useState } from 'react'
import { Users, ChevronRight, AlertTriangle, Clock, CheckCircle } from 'lucide-react'
import { useTeamTasks } from '../hooks/useTasks'
import { parseAssign, isOverdue, getInitials } from '../utils/dateUtils'
import TaskList from './TaskList'

export default function TeamView({ onSelectTask }) {
  const { data: tasks, isLoading } = useTeamTasks()
  const [selectedUser, setSelectedUser] = useState(null)

  // Group tasks by assignee
  const userMap = {}
  if (tasks) {
    tasks.forEach(task => {
      const assignees = parseAssign(task._assign)
      if (assignees.length === 0) {
        // Unassigned — group under owner
        const key = task.owner || 'unassigned'
        if (!userMap[key]) userMap[key] = { email: key, tasks: [] }
        userMap[key].tasks.push(task)
      } else {
        assignees.forEach(email => {
          if (!userMap[email]) userMap[email] = { email, tasks: [] }
          userMap[email].tasks.push(task)
        })
      }
    })
  }

  const userList = Object.values(userMap).sort((a, b) => {
    // Sort by overdue count descending
    const aOverdue = a.tasks.filter(t => isOverdue(t.exp_end_date)).length
    const bOverdue = b.tasks.filter(t => isOverdue(t.exp_end_date)).length
    return bOverdue - aOverdue
  })

  if (selectedUser) {
    const userData = userMap[selectedUser]
    return (
      <div>
        <div className="flex items-center gap-3 px-4 py-3 bg-white border-b sticky top-0 z-10">
          <button onClick={() => setSelectedUser(null)} className="p-1 -ml-1 text-gray-600">
            <ChevronRight size={20} className="rotate-180" />
          </button>
          <div className="w-8 h-8 rounded-full bg-frappe-blue text-white flex items-center justify-center text-sm font-medium">
            {getInitials(selectedUser)}
          </div>
          <div>
            <h2 className="text-sm font-bold text-gray-900">{selectedUser.split('@')[0]}</h2>
            <p className="text-xs text-gray-500">{userData?.tasks.length || 0} tasks</p>
          </div>
        </div>
        <TaskList
          tasks={userData?.tasks || []}
          onSelectTask={onSelectTask}
          isLoading={false}
        />
      </div>
    )
  }

  return (
    <div className="p-4">
      <h2 className="text-lg font-bold text-gray-900 mb-3 flex items-center gap-2">
        <Users size={20} /> Team Dashboard
      </h2>

      {isLoading ? (
        <div className="space-y-2">
          {[1, 2, 3, 4].map(i => <div key={i} className="h-16 bg-gray-100 rounded-lg animate-pulse" />)}
        </div>
      ) : userList.length === 0 ? (
        <p className="text-center text-gray-400 py-8 text-sm">No active team tasks</p>
      ) : (
        <div className="space-y-2">
          {userList.map(u => {
            const overdue = u.tasks.filter(t => isOverdue(t.exp_end_date)).length
            const working = u.tasks.filter(t => t.status === 'Working').length
            const review = u.tasks.filter(t => t.status === 'Pending Review').length
            return (
              <button
                key={u.email}
                onClick={() => setSelectedUser(u.email)}
                className="w-full text-left bg-white rounded-lg border shadow-sm p-3 active:bg-gray-50"
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2.5">
                    <div className="w-9 h-9 rounded-full bg-frappe-blue text-white flex items-center justify-center text-sm font-medium">
                      {getInitials(u.email)}
                    </div>
                    <div>
                      <p className="text-sm font-semibold text-gray-800">{u.email.split('@')[0]}</p>
                      <p className="text-xs text-gray-400">{u.tasks.length} tasks</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    {overdue > 0 && (
                      <span className="inline-flex items-center gap-0.5 text-xs font-semibold text-red-600 bg-red-50 px-1.5 py-0.5 rounded">
                        <AlertTriangle size={10} />{overdue}
                      </span>
                    )}
                    {working > 0 && (
                      <span className="inline-flex items-center gap-0.5 text-xs font-semibold text-yellow-700 bg-yellow-50 px-1.5 py-0.5 rounded">
                        <Clock size={10} />{working}
                      </span>
                    )}
                    {review > 0 && (
                      <span className="inline-flex items-center gap-0.5 text-xs font-semibold text-purple-700 bg-purple-50 px-1.5 py-0.5 rounded">
                        <CheckCircle size={10} />{review}
                      </span>
                    )}
                    <ChevronRight size={16} className="text-gray-400" />
                  </div>
                </div>
              </button>
            )
          })}
        </div>
      )}
    </div>
  )
}
