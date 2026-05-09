import React from 'react'
import { CheckSquare, FolderOpen, Users } from 'lucide-react'

export default function BottomNav({ activeView, onChangeView, isManager }) {
  const tabs = [
    { key: 'my-tasks', label: 'My Tasks', icon: CheckSquare },
    { key: 'projects', label: 'Projects', icon: FolderOpen },
  ]
  if (isManager) {
    tabs.push({ key: 'team', label: 'Team', icon: Users })
  }

  return (
    <nav className="fixed bottom-0 left-0 right-0 bg-white border-t flex safe-area-bottom z-40">
      {tabs.map(tab => {
        const Icon = tab.icon
        const active = activeView === tab.key
        return (
          <button
            key={tab.key}
            onClick={() => onChangeView(tab.key)}
            className={`flex-1 flex flex-col items-center py-2 ${
              active ? 'text-frappe-blue' : 'text-gray-400'
            }`}
          >
            <Icon size={20} strokeWidth={active ? 2.5 : 1.5} />
            <span className={`text-xs mt-0.5 ${active ? 'font-semibold' : 'font-medium'}`}>
              {tab.label}
            </span>
          </button>
        )
      })}
    </nav>
  )
}
