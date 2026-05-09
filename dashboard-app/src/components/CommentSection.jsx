import React, { useState, useRef, useEffect } from 'react'
import { Send, MessageSquare } from 'lucide-react'
import { useComments, useAddComment } from '../hooks/useComments'
import { timeAgo, getInitials } from '../utils/dateUtils'

export default function CommentSection({ taskName }) {
  const { data: comments, isLoading } = useComments(taskName)
  const addComment = useAddComment()
  const [text, setText] = useState('')
  const listRef = useRef(null)

  useEffect(() => {
    if (listRef.current) {
      listRef.current.scrollTop = 0
    }
  }, [comments])

  function handleSend() {
    const content = text.trim()
    if (!content) return
    addComment.mutate(
      { taskName, content },
      { onSuccess: () => setText('') }
    )
  }

  function handleKeyDown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  if (isLoading) {
    return (
      <div className="p-4 space-y-3">
        {[1, 2, 3].map(i => (
          <div key={i} className="animate-pulse flex gap-2">
            <div className="w-8 h-8 rounded-full bg-gray-200" />
            <div className="flex-1 space-y-1">
              <div className="h-3 bg-gray-200 rounded w-24" />
              <div className="h-4 bg-gray-100 rounded w-full" />
            </div>
          </div>
        ))}
      </div>
    )
  }

  return (
    <div className="flex flex-col h-full">
      {/* Comment list */}
      <div ref={listRef} className="flex-1 overflow-y-auto p-4 space-y-3">
        {(!comments || comments.length === 0) && (
          <div className="text-center py-8 text-gray-400">
            <MessageSquare size={32} className="mx-auto mb-2 opacity-50" />
            <p className="text-sm">No comments yet</p>
          </div>
        )}
        {comments && comments.map(c => (
          <div key={c.name} className="flex gap-2">
            <div className="shrink-0 w-7 h-7 rounded-full bg-gray-200 text-gray-600 flex items-center justify-center text-xs font-medium">
              {getInitials(c.comment_by || c.comment_email)}
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-baseline gap-2">
                <span className="text-xs font-semibold text-gray-700">{c.comment_by || c.comment_email}</span>
                <span className="text-xs text-gray-400">{timeAgo(c.creation)}</span>
              </div>
              <div
                className="text-sm text-gray-700 mt-0.5 break-words"
                dangerouslySetInnerHTML={{ __html: c.content }}
              />
            </div>
          </div>
        ))}
      </div>

      {/* Input bar */}
      <div className="sticky bottom-0 border-t bg-white px-3 py-2 flex items-end gap-2 safe-area-bottom">
        <textarea
          value={text}
          onChange={e => setText(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Add a comment..."
          rows={1}
          className="flex-1 rounded-xl border border-gray-200 px-3 py-2 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-frappe-blue/40"
          style={{ maxHeight: '100px' }}
        />
        <button
          onClick={handleSend}
          disabled={!text.trim() || addComment.isPending}
          className="shrink-0 w-9 h-9 rounded-full bg-frappe-blue text-white flex items-center justify-center disabled:opacity-40"
        >
          <Send size={16} />
        </button>
      </div>
    </div>
  )
}
