import { apiGet, apiPatch, apiPost } from './client'
import type { AuthUser } from './types'

export interface RegisterPayload {
  full_name: string
  display_name: string
  email: string
  password: string
}

export interface LoginPayload {
  email: string
  password: string
}

export interface ProfileUpdatePayload {
  full_name?: string
  display_name?: string
}

export function register(payload: RegisterPayload): Promise<AuthUser> {
  return apiPost<AuthUser>('/api/v1/auth/register', payload)
}

export function login(payload: LoginPayload): Promise<AuthUser> {
  return apiPost<AuthUser>('/api/v1/auth/login', payload)
}

export function loginWithGoogle(credential: string): Promise<AuthUser> {
  return apiPost<AuthUser>('/api/v1/auth/google', { credential })
}

export function logout(): Promise<void> {
  return apiPost<void>('/api/v1/auth/logout')
}

export function getCurrentUser(options: { signal?: AbortSignal } = {}): Promise<AuthUser> {
  return apiGet<AuthUser>('/api/v1/auth/me', options)
}

export function updateProfile(payload: ProfileUpdatePayload): Promise<AuthUser> {
  return apiPatch<AuthUser>('/api/v1/auth/me', payload)
}
