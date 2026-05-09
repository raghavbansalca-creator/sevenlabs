import { useQuery } from '@tanstack/react-query'
import { getLoggedUser, getDoc } from '../api/frappe'

export function useAuth() {
  const { data: user, isLoading, error } = useQuery({
    queryKey: ['auth'],
    queryFn: async () => {
      const email = await getLoggedUser()
      const userDoc = await getDoc('User', email)
      const roles = (userDoc.roles || []).map(r => r.role)
      return {
        email,
        fullName: userDoc.full_name || email,
        userImage: userDoc.user_image,
        roles,
        isManager: roles.includes('Projects Manager') || email === 'Administrator',
      }
    },
    staleTime: Infinity,
    retry: 1,
  })

  return { user, isLoading, error }
}
