import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getList, setValue, insertDoc, addAssignment, removeAssignment } from '../api/frappe'
import { TASK_FIELDS, ACTIVE_STATUSES } from '../utils/constants'

/**
 * Fetch logged-in user's active tasks
 */
export function useMyTasks(userEmail) {
  return useQuery({
    queryKey: ['my-tasks', userEmail],
    queryFn: () =>
      getList('Task', {
        fields: TASK_FIELDS,
        filters: [['status', 'in', ACTIVE_STATUSES]],
        orFilters: [
          ['owner', '=', userEmail],
          ['_assign', 'like', `%${userEmail}%`],
        ],
        orderBy: 'modified desc',
        limit: 200,
      }),
    enabled: !!userEmail,
    refetchInterval: 60000,
  })
}

/**
 * Fetch all active tasks (for manager team view)
 */
export function useTeamTasks() {
  return useQuery({
    queryKey: ['team-tasks'],
    queryFn: () =>
      getList('Task', {
        fields: TASK_FIELDS,
        filters: [['status', 'in', ACTIVE_STATUSES]],
        orderBy: 'modified desc',
        limit: 500,
      }),
    refetchInterval: 60000,
  })
}

/**
 * Fetch tasks for a specific project
 */
export function useProjectTasks(project) {
  return useQuery({
    queryKey: ['project-tasks', project],
    queryFn: () =>
      getList('Task', {
        fields: TASK_FIELDS,
        filters: [['project', '=', project]],
        orderBy: 'creation asc',
        limit: 500,
      }),
    enabled: !!project,
  })
}

/**
 * Fetch subtasks of a parent task
 */
export function useSubtasks(parentTask) {
  return useQuery({
    queryKey: ['subtasks', parentTask],
    queryFn: () =>
      getList('Task', {
        fields: TASK_FIELDS,
        filters: [['parent_task', '=', parentTask]],
        orderBy: 'creation asc',
        limit: 100,
      }),
    enabled: !!parentTask,
  })
}

/**
 * Fetch task lists for a project
 */
export function useTaskLists(project) {
  return useQuery({
    queryKey: ['task-lists', project],
    queryFn: () =>
      getList('Task List', {
        fields: ['name', 'title', 'project'],
        filters: [['project', '=', project]],
        limit: 100,
      }),
    enabled: !!project,
  })
}

/**
 * Fetch user's projects (distinct projects from their tasks)
 */
export function useMyProjects(userEmail) {
  return useQuery({
    queryKey: ['my-projects', userEmail],
    queryFn: async () => {
      const tasks = await getList('Task', {
        fields: ['project'],
        filters: [['status', 'in', ACTIVE_STATUSES]],
        orFilters: [
          ['owner', '=', userEmail],
          ['_assign', 'like', `%${userEmail}%`],
        ],
        limit: 500,
      })
      // Get unique projects
      const projectNames = [...new Set(tasks.map(t => t.project).filter(Boolean))]
      if (!projectNames.length) return []
      // Fetch project details
      return getList('Project', {
        fields: ['name', 'project_name', 'status', 'percent_complete'],
        filters: [['name', 'in', projectNames]],
        limit: 100,
      })
    },
    enabled: !!userEmail,
  })
}

/**
 * Fetch all active users (for assignment picker)
 */
export function useUsers() {
  return useQuery({
    queryKey: ['users'],
    queryFn: () =>
      getList('User', {
        fields: ['name', 'full_name', 'user_image', 'enabled'],
        filters: [['enabled', '=', 1], ['user_type', '=', 'System User']],
        limit: 200,
      }),
    staleTime: 300000, // 5 min
  })
}

/**
 * Update a single task field
 */
export function useUpdateTask() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ name, field, value }) => setValue('Task', name, field, value),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['my-tasks'] })
      queryClient.invalidateQueries({ queryKey: ['team-tasks'] })
      queryClient.invalidateQueries({ queryKey: ['project-tasks'] })
      queryClient.invalidateQueries({ queryKey: ['subtasks'] })
    },
  })
}

/**
 * Assign a user to a task
 */
export function useAssignTask() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ taskName, userEmail }) => addAssignment('Task', taskName, userEmail),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['my-tasks'] })
      queryClient.invalidateQueries({ queryKey: ['team-tasks'] })
      queryClient.invalidateQueries({ queryKey: ['project-tasks'] })
    },
  })
}

/**
 * Remove assignment
 */
export function useUnassignTask() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ taskName, userEmail }) => removeAssignment('Task', taskName, userEmail),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['my-tasks'] })
      queryClient.invalidateQueries({ queryKey: ['team-tasks'] })
    },
  })
}
