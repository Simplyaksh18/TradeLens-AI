import { createContext } from 'react'
import type { AuthUser } from '../api/types'
import type { LoginPayload, ProfileUpdatePayload, RegisterPayload } from '../api/auth'

export type AuthStatus = 'loading' | 'authenticated' | 'unauthenticated'

export interface AuthContextValue {
  user: AuthUser | null
  status: AuthStatus
  login: (payload: LoginPayload) => Promise<void>
  register: (payload: RegisterPayload) => Promise<void>
  loginWithGoogle: (credential: string) => Promise<void>
  logout: () => Promise<void>
  updateProfile: (payload: ProfileUpdatePayload) => Promise<void>
}

export const AuthContext = createContext<AuthContextValue | null>(null)
