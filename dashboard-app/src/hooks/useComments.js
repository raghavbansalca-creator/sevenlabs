import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getList, insertDoc, uploadFile as apiUploadFile } from '../api/frappe'

/**
 * Fetch comments for a task
 */
export function useComments(taskName) {
  return useQuery({
    queryKey: ['comments', taskName],
    queryFn: () =>
      getList('Comment', {
        fields: ['name', 'comment_by', 'comment_email', 'content', 'creation'],
        filters: [
          ['reference_doctype', '=', 'Task'],
          ['reference_name', '=', taskName],
          ['comment_type', '=', 'Comment'],
        ],
        orderBy: 'creation desc',
        limit: 50,
      }),
    enabled: !!taskName,
  })
}

/**
 * Add a comment to a task
 */
export function useAddComment() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ taskName, content }) =>
      insertDoc({
        doctype: 'Comment',
        comment_type: 'Comment',
        reference_doctype: 'Task',
        reference_name: taskName,
        content,
      }),
    onSuccess: (_, { taskName }) => {
      queryClient.invalidateQueries({ queryKey: ['comments', taskName] })
    },
  })
}

/**
 * Fetch file attachments for a task
 */
export function useAttachments(taskName) {
  return useQuery({
    queryKey: ['attachments', taskName],
    queryFn: () =>
      getList('File', {
        fields: ['name', 'file_name', 'file_url', 'file_size', 'creation', 'owner'],
        filters: [
          ['attached_to_doctype', '=', 'Task'],
          ['attached_to_name', '=', taskName],
        ],
        orderBy: 'creation desc',
        limit: 20,
      }),
    enabled: !!taskName,
  })
}

/**
 * Upload a file attachment
 */
export function useUploadFile() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ file, taskName }) => apiUploadFile(file, 'Task', taskName),
    onSuccess: (_, { taskName }) => {
      queryClient.invalidateQueries({ queryKey: ['attachments', taskName] })
    },
  })
}
