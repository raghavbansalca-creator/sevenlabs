import React, { useState, useCallback } from 'react'
import { useAuth } from './hooks/useAuth'
import { useMyTasks } from './hooks/useTasks'
import TaskList from './components/TaskList'
import TaskDetail from './components/TaskDetail'
import ProjectView from './components/ProjectView'
import TeamView from './components/TeamView'
import BottomNav from './components/BottomNav'
import { RefreshCw } from 'lucide-react'
import { useQueryClient } from '@tanstack/react-query'

export default function App() {
  const { user, isLoading: authLoading, error: authError } = useAuth()
  const { data: tasks, isLoading: tasksLoading, refetch } = useMyTasks(user?.email)
  const [view, setView] = useState('my-tasks')
  const [selectedTask, setSelectedTask] = useState(null)
  const [taskHistory, setTaskHistory] = useState([])
  const queryClient = useQueryClient()

  const handleSelectTask = useCallback((task) => {
    if (selectedTask) {
      setTaskHistory(prev => [...prev, selectedTask])
    }
    setSelectedTask(task)
  }, [selectedTask])

  const handleBack = useCallback(() => {
    if (taskHistory.length > 0) {
      const prev = taskHistory[taskHistory.length - 1]
      setTaskHistory(h => h.slice(0, -1))
      setSelectedTask(prev)
    } else {
      setSelectedTask(null)
    }
  }, [taskHistory])

  // Auth loading
  if (authLoading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="animate-spin w-8 h-8 border-3 border-frappe-blue border-t-transparent rounded-full" />
      </div>
    )
  }

  // Auth error
  if (authError || !user) {
    return (
      <div className="flex flex-col items-center justify-center h-screen px-6 text-center">
        <p className="text-lg font-semibold text-red-600 mb-2">Authentication Error</p>
        <p className="text-sm text-gray-500 mb-4">Please log in to ERPNext first.</p>
        <a href="/login" className="px-4 py-2 bg-frappe-blue text-white rounded-lg text-sm font-medium">
          Go to Login
        </a>
      </div>
    )
  }

  // Task detail overlay
  if (selectedTask) {
    return (
      <TaskDetail
        task={selectedTask}
        onBack={handleBack}
        onSelectTask={handleSelectTask}
      />
    )
  }

  return (
    <div className="min-h-screen bg-gray-50 pb-16">
      {/* Header */}
      <header className="bg-white border-b sticky top-0 z-30 px-4 py-3">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-lg font-bold text-gray-900">
              {view === 'my-tasks' ? 'My Tasks' : view === 'projects' ? 'Projects' : 'Team'}
            </h1>
            <p className="text-xs text-gray-500">{user.fullName}</p>
          </div>
          <button
            onClick={() => {
              queryClient.invalidateQueries()
              refetch()
            }}
            className="p-2 text-gray-500 active:text-frappe-blue"
          >
            <RefreshCw size={18} />
          </button>
        </div>
      </header>

      {/* Content */}
      {view === 'my-tasks' && (
        <TaskList
          tasks={tasks}
          onSelectTask={handleSelectTask}
          isLoading={tasksLoading}
        />
      )}

      {view === 'projects' && (
        <ProjectView
          userEmail={user.email}
          onSelectTask={handleSelectTask}
        />
      )}

      {view === 'team' && user.isManager && (
        <TeamView onSelectTask={handleSelectTask} />
      )}

      {/* Bottom Nav */}
      <BottomNav
        activeView={view}
        onChangeView={setView}
        isManager={user.isManager}
      />
    </div>
  )
}
