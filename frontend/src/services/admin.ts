import { api } from './api'
import type { User, UserRole } from './auth'
import type { PlanSummary, SubscriptionSummary, UsageMetric } from './subscription'

export interface AdminPlan extends PlanSummary {
  active: boolean
}

export interface AuditEvent {
  id: string
  user_id: string | null
  actor_user_id: string | null
  entity_type: string
  entity_id: string | null
  event_type: string
  event_data_json: Record<string, unknown> | null
  created_at: string
}

export interface EntitlementOverride {
  id: string
  user_id: string
  created_by_user_id: string | null
  revoked_by_user_id: string | null
  monthly_story_limit: number | null
  max_pages_per_story: number | null
  image_quality_mode: string | null
  voice_clone_limit: number | null
  monthly_audio_chars_limit: number | null
  reason: string
  effective_from: string
  effective_to: string | null
  revoked_at: string | null
  created_at: string
  updated_at: string
}

export interface UsageCreditGrant {
  id: string
  user_id: string
  created_by_user_id: string | null
  revoked_by_user_id: string | null
  usage_type: string
  quantity: number
  reason: string
  effective_from: string
  effective_to: string | null
  revoked_at: string | null
  created_at: string
  updated_at: string
}

export interface AdminUserListItem extends User {
  current_period_start: string | null
  current_period_end: string | null
  plan: PlanSummary
  usage: Record<string, UsageMetric>
}

export interface AdminUserDetail extends AdminUserListItem {
  active_override: EntitlementOverride | null
  active_grants: UsageCreditGrant[]
  recent_audit_events: AuditEvent[]
}

export interface PlanUpdatePayload {
  name?: string
  monthly_story_limit?: number
  max_pages_per_story?: number
  image_quality_mode?: string
  voice_clone_limit?: number
  monthly_audio_chars_limit?: number
  price_cents?: number
  active?: boolean
}

export interface CreateEntitlementOverridePayload {
  reason: string
  effective_to?: string | null
  monthly_story_limit?: number | null
  max_pages_per_story?: number | null
  image_quality_mode?: string | null
  voice_clone_limit?: number | null
  monthly_audio_chars_limit?: number | null
}

export interface CreateUsageGrantPayload {
  usage_type: string
  quantity: number
  reason: string
  effective_to?: string | null
}

export async function getAdminUsers(query?: string) {
  const { data } = await api.get<AdminUserListItem[]>('/admin/users', {
    params: query ? { q: query } : undefined,
  })
  return data
}

export async function getAdminUserDetail(userId: string) {
  const { data } = await api.get<AdminUserDetail>(`/admin/users/${userId}`)
  return data
}

export async function getAdminPlans() {
  const { data } = await api.get<AdminPlan[]>('/admin/plans')
  return data
}

export async function updateAdminPlan(planCode: string, payload: PlanUpdatePayload) {
  const { data } = await api.patch<AdminPlan>(`/admin/plans/${planCode}`, payload)
  return data
}

export async function updateAdminUserRole(userId: string, role: UserRole) {
  const { data } = await api.patch<User>(`/admin/users/${userId}/role`, { role })
  return data
}

export async function assignAdminUserSubscription(userId: string, planCode: string) {
  const { data } = await api.post<SubscriptionSummary>(`/admin/users/${userId}/subscription`, {
    plan_code: planCode,
  })
  return data
}

export async function createAdminEntitlementOverride(
  userId: string,
  payload: CreateEntitlementOverridePayload,
) {
  const { data } = await api.post<EntitlementOverride>(`/admin/users/${userId}/entitlement-overrides`, payload)
  return data
}

export async function revokeAdminEntitlementOverride(overrideId: string) {
  const { data } = await api.post<EntitlementOverride>(`/admin/entitlement-overrides/${overrideId}/revoke`)
  return data
}

export async function createAdminUsageGrant(userId: string, payload: CreateUsageGrantPayload) {
  const { data } = await api.post<UsageCreditGrant>(`/admin/users/${userId}/usage-grants`, payload)
  return data
}

export async function revokeAdminUsageGrant(grantId: string) {
  const { data } = await api.post<UsageCreditGrant>(`/admin/usage-grants/${grantId}/revoke`)
  return data
}
