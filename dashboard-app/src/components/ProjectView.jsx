import React, { useState } from 'react'
import { ArrowLeft, FolderOpen, ChevronDown, ChevronRight } from 'lucide-react'
import { useMyProjects, useProjectTasks, useTaskLists } from '../hooks/useTasks'
import TaskCard from './TaskCard'

function TaskListGroup({ name, tasks, allTasks, onSelectTask }) {
  const [open, setOpen] = useState(true)
  const parentTasks = tasks.filter(t => !t.parent_task)

  return (
    <div className="mb-3 bg-white rounded-lg border shadow-sm overflow-hidden">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between px-3 py-2.5 bg-gray-50 border-b"
      >
        <div className="flex items-center gap-2">
          {open ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
          <FolderOpen size={14} className="text-blue-500" />
          <span className="text-sm font-semibold text-gray-700">{name}</span>
        </div>
        <span className="text-xs bg-gray-200 text-gray-600 px-2 py-0.5 rounded-full font-medium">
          {tasks.length}
        </span>
      </button>
      {open && (
        <div className="p-2 space-y-2">
          {parentTasks.length === 0 && (
            <p className="text-xs text-gray-400 text-center py-3">No tasks in this list</p>
          )}
          {parentTasks.map(task => (
            <TaskCard key={task.name} task={task} onSelect={onSelectTask} />
          ))}
        </div>
      )}
    </div>
  )
}

function ProjectDetail({ project, onBack, onSelectTask }) {
  const { data: tasks, isLoading: tasksLoading } = useProjectTasks(project.name)
  const { data: taskLists } = useTaskLists(project.name)

  const groupedByList = {}
  const unassigned = []

  if (tasks) {
    tasks.forEach(t => {
      if (t.custom_task_list) {
        if (!groupedByList[t.custom_task_list]) groupedByList[t.custom_task_list] = []
        groupedByList[t.custom_task_list].push(t)
      } else {
        unassigned.push(t)
      }
    })
  }

  return (
    <div>
      <div className="flex items-center gap-3 px-4 py-3 bg-white border-b sticky top-0 z-10">
        <button onClick={onBack} className="p-1 -ml-1"><ArrowLeft size={20} /></button>
        <div className="flex-1 min-w-0">
          <h2 className="text-base font-bold text-gray-900 truncate">{project.project_name || project.name}</h2>
          <p className="text-xs text-gray-500">{tasks ? tasks.length : 0} tasks</p>
        </div>
      </div>

      {tasksLoading ? (
        <div className="p-4 space-y-3">
          {[1, 2, 3].map(i => <div key={i} className="h-20 bg-gray-100 rounded-lg animate-pulse" />)}
        </div>
      ) : (
        <div className="p-4">
          {taskLists && taskLists.map(tl => (
            <TaskListGroup
              key={tl.name}
              name={tl.title || tl.name}
              tasks={groupedByList[tl.name] || []}
              allTasks={tasks || []}
              onSelectTask={onSelectTask}
            />
          ))}
          {unassigned.length > 0 && (
            <TaskListGroup
              name="Unassigned Tasks"
              tasks={unassigned}
              allTasks={tasks || []}
              onSelectTask={onSelectTask}
            />
          )}
          {(!tasks || tasks.length === 0) && (
            <p className="text-center text-gray-400 py-8 text-sm">No tasks in this project</p>
          )}
        </div>
      )}
    </div>
  )
}

export default function ProjectView({ userEmail, onSelectTask }) {
  const { data: projects, isLoading } = useMyProjects(userEmail)
  const [selectedProject, setSelectedProject] = useState(null)

  if (selectedProject) {
    return (
      <ProjectDetail
        project={selectedProject}
        onBack={() => setSelectedProject(null)}
        onSelectTask={onSelectTask}
      />
    )
  }

  return (
    <div className="p-4">
      <h2 className="text-lg font-bold text-gray-900 mb-3">Projects</h2>
      {isLoading ? (
        <div className="space-y-2">
          {[1, 2, 3].map(i => <div key={i} className="h-16 bg-gray-100 rounded-lg animate-pulse" />)}
        </div>
      ) : !projects || projects.length === 0 ? (
        <p className="text-center text-gray-400 py-8 text-sm">No active projects</p>
      ) : (
        <div className="space-y-2">
          {projects.map(p => (
            <button
              key={p.name}
              onClick={() => setSelectedProject(p)}
              className="w-full text-left bg-white rounded-lg border shadow-sm p-3 active:bg-gray-50"
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <FolderOpen size={16} className="text-blue-500" />
                  <span className="text-sm font-semibold text-gray-800">{p.project_name || p.name}</span>
                </div>
                <ChevronRight size={16} className="text-gray-400" />
              </div>
              {p.percent_complete != null && (
                <div className="mt-2 w-full bg-gray-100 rounded-full h-1.5">
                  <div className="h-1.5 rounded-full bg-frappe-blue" style={{ width: `${p.percent_complete}%` }} />
                </div>
              )}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
