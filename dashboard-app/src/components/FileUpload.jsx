import React, { useRef, useState } from 'react'
import { Paperclip, Upload, FileText, Image, File, Download } from 'lucide-react'
import { useAttachments, useUploadFile } from '../hooks/useComments'
import { timeAgo } from '../utils/dateUtils'

function FileIcon({ name }) {
  const ext = (name || '').split('.').pop().toLowerCase()
  if (['jpg', 'jpeg', 'png', 'gif', 'webp', 'svg'].includes(ext)) return <Image size={16} className="text-green-500" />
  if (['pdf', 'doc', 'docx', 'xls', 'xlsx'].includes(ext)) return <FileText size={16} className="text-red-500" />
  return <File size={16} className="text-gray-500" />
}

function formatSize(bytes) {
  if (!bytes) return ''
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

export default function FileUpload({ taskName }) {
  const { data: attachments, isLoading } = useAttachments(taskName)
  const uploadFile = useUploadFile()
  const fileRef = useRef(null)
  const [uploading, setUploading] = useState(false)

  async function handleFileSelect(e) {
    const file = e.target.files?.[0]
    if (!file) return
    setUploading(true)
    uploadFile.mutate(
      { file, taskName },
      {
        onSettled: () => {
          setUploading(false)
          if (fileRef.current) fileRef.current.value = ''
        },
      }
    )
  }

  return (
    <div className="p-4">
      {/* Upload button */}
      <button
        onClick={() => fileRef.current?.click()}
        disabled={uploading}
        className="w-full flex items-center justify-center gap-2 border-2 border-dashed border-gray-300 rounded-xl py-4 text-sm font-medium text-gray-500 active:bg-gray-50 disabled:opacity-50"
      >
        {uploading ? (
          <span className="animate-spin w-4 h-4 border-2 border-frappe-blue border-t-transparent rounded-full" />
        ) : (
          <Upload size={18} />
        )}
        {uploading ? 'Uploading...' : 'Attach File'}
      </button>
      <input
        ref={fileRef}
        type="file"
        accept="image/*,.pdf,.doc,.docx,.xls,.xlsx,.csv,.txt,.zip"
        onChange={handleFileSelect}
        className="hidden"
      />

      {/* Attachments list */}
      <div className="mt-4 space-y-2">
        {isLoading && (
          <div className="space-y-2">
            {[1, 2].map(i => <div key={i} className="h-14 bg-gray-100 rounded-lg animate-pulse" />)}
          </div>
        )}

        {attachments && attachments.length === 0 && !isLoading && (
          <div className="text-center py-8 text-gray-400">
            <Paperclip size={32} className="mx-auto mb-2 opacity-50" />
            <p className="text-sm">No attachments yet</p>
          </div>
        )}

        {attachments && attachments.map(att => (
          <a
            key={att.name}
            href={att.file_url}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-3 bg-gray-50 rounded-lg p-3 active:bg-gray-100"
          >
            <FileIcon name={att.file_name} />
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-gray-800 truncate">{att.file_name}</p>
              <p className="text-xs text-gray-400">
                {formatSize(att.file_size)} {att.creation && `\u00b7 ${timeAgo(att.creation)}`}
              </p>
            </div>
            <Download size={16} className="text-gray-400 shrink-0" />
          </a>
        ))}
      </div>
    </div>
  )
}
