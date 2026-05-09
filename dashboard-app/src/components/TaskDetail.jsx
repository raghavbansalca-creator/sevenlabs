import React, { useState } from 'react'
import { ArrowLeft, ChevronDown, Paperclip, MessageSquare, ListTree } from 'lucide-react'
import { STATUS_CONFIG, PRIORITY_CONFIG, STATUSES, PRIORITIES } from '../utils/constants'
import { stripTime, formatDateFull, parseAssign, getInitials } from '../utils/dateUtils'
import { useUpdateTask, useSubtasks, useUsers, useAssignTask } from '../hooks/useTasks'
import CommentSection from './CommentSection'
import FileUpload from './FileUpload'

export default function TaskDetail({ task, onBack, onSelectTask }) {
  const updateTask = useUpdateTask()
  const assignTask = useAssignTask()
  const { data: subtasks } = useSubtasks(task.is_group ? task.name : null)
  const { data: users } = useUsers()
  const [showAssignPicker, setShowAssignPicker] = useState(false)
  const [activeTab, setActiveTab] = useState('details')
  const [toast, setToast] = useState(null)

  const assignees = parseAssign(task._assign)
  const status = STATUS_CONFIG[task.status] || STATUS_CONFIG.Open

  function handleUpdate(field, value) {
    updateTask.mutate(
      { name: task.name, field, value },
      {
        onSuccess: () => showToast('Updated'),
        onError: (err) => showToast(err.message, true),
      }
    )
  }

  function handleAssign(email) {
    assignTask.mutate(
      { taskName: task.name, userEmail: email },
      {
        onSuccess: () => { setShowAssignPicker(false); showToast('Assigned') },
        onError: (err) => showToast(err.message, true),
      }
    )
  }

  function showToast(msg, isError = false) {
    setToast({ msg, isError })
    setTimeout(() => setToast(null), 2000)
  }

  return (
    <div className="fixed inset-0 bg-white z-50 flex flex-col">
      {/* Header */}
      <div className={`flex items-center gap-3 px-4 py-3 border-b ${status.bg}`}>
        <button onClick={onBack} className="p-1 -ml-1">
          <ArrowLeft size={20} />
        </button>
        <div className="flex-1 min-w-0">
          <h2 className="text-base font-bold text-gray-900 truncate">{task.subject}</h2>
          {task.project && <p className="text-xs text-gray-500">{task.project}</p>}
        </div>
      </div>

      {/* Tab bar */}
      <div className="flex border-b bg-white">
        {[
          { key: 'details', label: 'Details' },
          { key: 'comments', label: 'Comments', icon: MessageSquare },
          { key: 'files', label: 'Files', icon: Paperclip },
        ].map(tab => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={`flex-1 py-2.5 text-xs font-semibold text-center border-b-2 ${
              activeTab === tab.key ? 'border-frappe-blue text-frappe-blue' : 'border-transparent text-gray-500'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto">
        {activeTab === 'details' && (
          <div className="p-4 space-y-4">
            {/* Status + Priority */}
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-xs font-medium text-gray-500 mb-1 block">Status</label>
                <select
                  value={task.status}
                  onChange={e => handleUpdate('status', e.target.value)}
                  className={`w-full rounded-lg border px-3 py-2.5 text-sm font-semibold ${status.bg} ${status.text}`}
                >
                  {STATUSES.map(s => <option key={s} value={s}>{s}</option>)}
                </select>
              </div>
              <div>
                <label className="text-xs font-medium text-gray-500 mb-1 block">Priority</label>
                <select
                  value={task.priority}
                  onChange={e => handleUpdate('priority', e.target.value)}
                  className={`w-full rounded-lg border px-3 py-2.5 text-sm font-semibold ${(PRIORITY_CONFIG[task.priority] || {}).bg} ${(PRIORITY_CONFIG[task.priority] || {}).text}`}
                >
                  {PRIORITIES.map(p => <option key={p} value={p}>{p}</option>)}
                </select>
              </div>
            </div>

            {/* Dates */}
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-xs font-medium text-gray-500 mb-1 block">Start Date</label>
                <input
                  type="date"
                  value={stripTime(task.exp_start_date)}
                  onChange={e => handleUpdate('exp_start_date', e.target.value || null)}
                  className="w-full rounded-lg border border-gray-200 px-3 py-2.5 text-sm"
                />
              </div>
              <div>
                <label className="text-xs font-medium text-gray-500 mb-1 block">End Date</label>
                <input
                  type="date"
                  value={stripTime(task.exp_end_date)}
                  onChange={e => handleUpdate('exp_end_date', e.target.value || null)}
                  className="w-full rounded-lg border border-gray-200 px-3 py-2.5 text-sm"
                />
              </div>
            </div>

            {/* Progress */}
            <div>
              <label className="text-xs font-medium text-gray-500 mb-1 block">
                Progress — {task.progress || 0}%
              </label>
              <input
                type="range"
                min="0"
                max="100"
                step="5"
                value={task.progress || 0}
                onChange={e => handleUpdate('progress', parseInt(e.target.value))}
                className="w-full accent-frappe-blue"
              />
            </div>

            {/* Assigned */}
            <div>
              <label className="text-xs font-medium text-gray-500 mb-1 block">Assigned To</label>
              <div className="flex flex-wrap gap-2">
                {assignees.map(email => (
                  <span key={email} className="inline-flex items-center gap-1 bg-blue-50 text-blue-700 px-2 py-1 rounded-full text-xs font-medium">
                    <span className="w-5 h-5 rounded-full bg-frappe-blue text-white flex items-center justify-center text-xs">
                      {getInitials(email)}
                    </span>
                    {email.split('@')[0]}
                  </span>
                ))}
                <button
                  onClick={() => setShowAssignPicker(!showAssignPicker)}
                  className="inline-flex items-center gap-1 bg-gray-100 text-gray-600 px-2 py-1 rounded-full text-xs font-medium"
                >
                  + Assign
                </button>
              </div>
              {showAssignPicker && users && (
                <div className="mt-2 bg-white border rounded-lg shadow-lg max-h-48 overflow-y-auto">
                  {users.filter(u => !assignees.includes(u.name)).map(u => (
                    <button
                      key={u.name}
                      onClick={() => handleAssign(u.name)}
                      className="w-full text-left px-3 py-2 text-sm hover:bg-blue-50 border-b border-gray-50"
                    >
                      {u.full_name || u.name}
                    </button>
                  ))}
                </div>
              )}
            </div>

            {/* Description */}
            {task.description && (
              <div>
                <label className="text-xs font-medium text-gray-500 mb-1 block">Description</label>
                <div
                  className="text-sm text-gray-700 bg-gray-50 rounded-lg p-3 prose prose-sm max-w-none"
                  dangerouslySetInnerHTML={{ __html: task.description }}
                />
              </div>
            )}

            {/* Subtasks */}
            {task.is_group === 1 && subtasks && subtasks.length > 0 && (
              <div>
                <label className="text-xs font-medium text-gray-500 mb-2 flex items-center gap-1">
                  <ListTree size={14} /> Subtasks ({subtasks.length})
                </label>
                <div className="space-y-1.5">
                  {subtasks.map(sub => {
                    const subStatus = STATUS_CONFIG[sub.status] || STATUS_CONFIG.Open
                    return (
                      <button
                        key={sub.name}
                        onClick={() => onSelectTask(sub)}
                        className="w-full text-left flex items-center gap-2 bg-gray-50 rounded-lg p-2.5 active:bg-gray-100"
                      >
                        <span className={`shrink-0 w-2 h-2 rounded-full ${subStatus.border.replace('border-', 'bg-')}`} />
                        <span className="text-sm text-gray-800 truncate flex-1">{sub.subject}</span>
                        <span className={`text-xs px-1.5 py-0.5 rounded ${subStatus.bg} ${subStatus.text}`}>
                          {sub.status}
                        </span>
                      </button>
                    )
                  })}
                </div>
              </div>
            )}

            {/* Meta */}
            <div className="text-xs text-gray-400 pt-2 border-t space-y-0.5">
              <p>Task ID: {task.name}</p>
              {task.creation && <p>Created: {formatDateFull(task.creation)}</p>}
              {task.modified && <p>Modified: {formatDateFull(task.modified)}</p>}
            </div>
          </div>
        )}

        {activeTab === 'comments' && (
          <CommentSection taskName={task.name} />
        )}

        {activeTab === 'files' && (
          <FileUpload taskName={task.name} />
        )}
      </div>

      {/* Toast */}
      {toast && (
        <div className={`fixed bottom-20 left-1/2 -translate-x-1/2 px-4 py-2 rounded-full text-sm font-medium shadow-lg z-[60] ${
          toast.isError ? 'bg-red-600 text-white' : 'bg-green-600 text-white'
        }`}>
          {toast.msg}
        </div>
      )}
    </div>
  )
}
