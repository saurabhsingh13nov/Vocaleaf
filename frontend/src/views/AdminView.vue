<script setup lang="ts">
import axios from 'axios'
import { computed, onMounted, reactive, ref, watch } from 'vue'

import { useAuth } from '@/composables/useAuth'
import {
  assignAdminUserSubscription,
  createAdminEntitlementOverride,
  createAdminUsageGrant,
  getAdminPlans,
  getAdminUserDetail,
  getAdminUsers,
  revokeAdminEntitlementOverride,
  revokeAdminUsageGrant,
  updateAdminPlan,
  updateAdminUserRole,
  type AdminPlan,
  type AdminUserListItem,
  type AdminUserDetail,
} from '@/services/admin'
import type { UserRole } from '@/services/auth'

const auth = useAuth()

const users = ref<AdminUserListItem[]>([])
const selectedUserId = ref<string | null>(null)
const selectedUser = ref<AdminUserDetail | null>(null)
const plans = ref<AdminPlan[]>([])
const searchQuery = ref('')
const pageError = ref<string | null>(null)
const pageMessage = ref<string | null>(null)
const isLoadingUsers = ref(false)
const isLoadingUserDetail = ref(false)
const isLoadingPlans = ref(false)
const isSavingRole = ref(false)
const isAssigningPlan = ref(false)
const isSavingOverride = ref(false)
const isSavingGrant = ref(false)
const savingPlanCode = ref<string | null>(null)

const roleForm = reactive<{ role: UserRole }>({ role: 'customer' })
const subscriptionForm = reactive({ plan_code: 'free' })
const overrideForm = reactive({
  reason: '',
  effective_to: '',
  monthly_story_limit: '',
  max_pages_per_story: '',
  image_quality_mode: '',
  voice_clone_limit: '',
  monthly_audio_chars_limit: '',
})
const grantForm = reactive({
  usage_type: 'stories_created',
  quantity: '1',
  reason: '',
  effective_to: '',
})
const planDrafts = reactive<Record<string, {
  name: string
  monthly_story_limit: string
  max_pages_per_story: string
  image_quality_mode: string
  voice_clone_limit: string
  monthly_audio_chars_limit: string
  price_cents: string
  active: boolean
}>>({})

const usageLabels: Record<string, string> = {
  stories_created: 'Stories created',
  voice_clones_created: 'Voice clones',
  audio_chars_synthesized: 'Narration characters',
  images_generated: 'Images generated',
}

const canEditPlans = computed(() => auth.user.value?.role === 'admin')
const canEditRoles = computed(() => auth.user.value?.role === 'admin')

function getErrorMessage(error: unknown) {
  if (axios.isAxiosError(error)) {
    const detail = error.response?.data?.detail

    if (typeof detail === 'string' && detail.trim().length > 0) {
      return detail
    }
  }

  return 'Something went wrong. Please try again.'
}

function optionalNumber(value: string) {
  const trimmed = value.trim()
  if (!trimmed) {
    return null
  }

  const parsed = Number(trimmed)
  return Number.isFinite(parsed) ? parsed : null
}

function optionalString(value: string) {
  const trimmed = value.trim()
  return trimmed.length > 0 ? trimmed : null
}

function optionalIsoDate(value: string) {
  const trimmed = value.trim()
  return trimmed ? new Date(trimmed).toISOString() : null
}

function syncPlanDrafts(nextPlans: AdminPlan[]) {
  for (const plan of nextPlans) {
    planDrafts[plan.code] = {
      name: plan.name,
      monthly_story_limit: plan.monthly_story_limit === null ? '' : String(plan.monthly_story_limit),
      max_pages_per_story: plan.max_pages_per_story === null ? '' : String(plan.max_pages_per_story),
      image_quality_mode: plan.image_quality_mode ?? '',
      voice_clone_limit: plan.voice_clone_limit === null ? '' : String(plan.voice_clone_limit),
      monthly_audio_chars_limit: plan.monthly_audio_chars_limit === null ? '' : String(plan.monthly_audio_chars_limit),
      price_cents: String(plan.price_cents),
      active: plan.active,
    }
  }
}

function createPlanDraft(plan: AdminPlan) {
  return {
    name: plan.name,
    monthly_story_limit: plan.monthly_story_limit === null ? '' : String(plan.monthly_story_limit),
    max_pages_per_story: plan.max_pages_per_story === null ? '' : String(plan.max_pages_per_story),
    image_quality_mode: plan.image_quality_mode ?? '',
    voice_clone_limit: plan.voice_clone_limit === null ? '' : String(plan.voice_clone_limit),
    monthly_audio_chars_limit: plan.monthly_audio_chars_limit === null ? '' : String(plan.monthly_audio_chars_limit),
    price_cents: String(plan.price_cents),
    active: plan.active,
  }
}

function planDraft(plan: AdminPlan) {
  let draft = planDrafts[plan.code]
  if (!draft) {
    draft = createPlanDraft(plan)
    planDrafts[plan.code] = draft
  }
  return draft
}

function syncSelectedUserForms(user: AdminUserDetail | null) {
  roleForm.role = (user?.role ?? 'customer') as UserRole
  subscriptionForm.plan_code = user?.plan.code ?? plans.value[0]?.code ?? 'free'
}

async function loadPlans() {
  isLoadingPlans.value = true

  try {
    const nextPlans = await getAdminPlans()
    plans.value = nextPlans
    syncPlanDrafts(nextPlans)
    const [firstPlan] = nextPlans
    if (!subscriptionForm.plan_code && firstPlan) {
      subscriptionForm.plan_code = firstPlan.code
    }
  } finally {
    isLoadingPlans.value = false
  }
}

async function loadUsers() {
  isLoadingUsers.value = true
  pageError.value = null

  try {
    const list = await getAdminUsers(searchQuery.value.trim() || undefined)
    users.value = list
    if (!selectedUserId.value || !list.some((user) => user.id === selectedUserId.value)) {
      selectedUserId.value = list[0]?.id ?? null
    }
  } catch (error) {
    pageError.value = getErrorMessage(error)
  } finally {
    isLoadingUsers.value = false
  }
}

async function loadUserDetail(userId: string) {
  isLoadingUserDetail.value = true
  pageError.value = null

  try {
    selectedUser.value = await getAdminUserDetail(userId)
    syncSelectedUserForms(selectedUser.value)
  } catch (error) {
    selectedUser.value = null
    pageError.value = getErrorMessage(error)
  } finally {
    isLoadingUserDetail.value = false
  }
}

async function reloadUserState() {
  await Promise.allSettled([
    loadUsers(),
    selectedUserId.value ? loadUserDetail(selectedUserId.value) : Promise.resolve(),
  ])
}

async function handleSearch() {
  await loadUsers()
  if (selectedUserId.value) {
    await loadUserDetail(selectedUserId.value)
  }
}

async function saveRole() {
  if (!selectedUser.value) {
    return
  }

  isSavingRole.value = true
  pageError.value = null
  pageMessage.value = null

  try {
    await updateAdminUserRole(selectedUser.value.id, roleForm.role)
    pageMessage.value = 'User role updated.'
    await reloadUserState()
  } catch (error) {
    pageError.value = getErrorMessage(error)
  } finally {
    isSavingRole.value = false
  }
}

async function assignPlan() {
  if (!selectedUser.value) {
    return
  }

  isAssigningPlan.value = true
  pageError.value = null
  pageMessage.value = null

  try {
    await assignAdminUserSubscription(selectedUser.value.id, subscriptionForm.plan_code)
    pageMessage.value = 'Subscription updated.'
    await reloadUserState()
  } catch (error) {
    pageError.value = getErrorMessage(error)
  } finally {
    isAssigningPlan.value = false
  }
}

async function saveOverride() {
  if (!selectedUser.value) {
    return
  }

  isSavingOverride.value = true
  pageError.value = null
  pageMessage.value = null

  try {
    await createAdminEntitlementOverride(selectedUser.value.id, {
      reason: overrideForm.reason.trim(),
      effective_to: optionalIsoDate(overrideForm.effective_to),
      monthly_story_limit: optionalNumber(overrideForm.monthly_story_limit),
      max_pages_per_story: optionalNumber(overrideForm.max_pages_per_story),
      image_quality_mode: optionalString(overrideForm.image_quality_mode),
      voice_clone_limit: optionalNumber(overrideForm.voice_clone_limit),
      monthly_audio_chars_limit: optionalNumber(overrideForm.monthly_audio_chars_limit),
    })
    overrideForm.reason = ''
    overrideForm.effective_to = ''
    overrideForm.monthly_story_limit = ''
    overrideForm.max_pages_per_story = ''
    overrideForm.image_quality_mode = ''
    overrideForm.voice_clone_limit = ''
    overrideForm.monthly_audio_chars_limit = ''
    pageMessage.value = 'Entitlement override created.'
    await reloadUserState()
  } catch (error) {
    pageError.value = getErrorMessage(error)
  } finally {
    isSavingOverride.value = false
  }
}

async function revokeOverride(overrideId: string) {
  pageError.value = null
  pageMessage.value = null

  try {
    await revokeAdminEntitlementOverride(overrideId)
    pageMessage.value = 'Entitlement override revoked.'
    await reloadUserState()
  } catch (error) {
    pageError.value = getErrorMessage(error)
  }
}

async function saveGrant() {
  if (!selectedUser.value) {
    return
  }

  isSavingGrant.value = true
  pageError.value = null
  pageMessage.value = null

  try {
    await createAdminUsageGrant(selectedUser.value.id, {
      usage_type: grantForm.usage_type,
      quantity: optionalNumber(grantForm.quantity) ?? 1,
      reason: grantForm.reason.trim(),
      effective_to: optionalIsoDate(grantForm.effective_to),
    })
    grantForm.quantity = '1'
    grantForm.reason = ''
    grantForm.effective_to = ''
    pageMessage.value = 'Usage grant created.'
    await reloadUserState()
  } catch (error) {
    pageError.value = getErrorMessage(error)
  } finally {
    isSavingGrant.value = false
  }
}

async function revokeGrant(grantId: string) {
  pageError.value = null
  pageMessage.value = null

  try {
    await revokeAdminUsageGrant(grantId)
    pageMessage.value = 'Usage grant revoked.'
    await reloadUserState()
  } catch (error) {
    pageError.value = getErrorMessage(error)
  }
}

async function savePlan(planCode: string) {
  const draft = planDrafts[planCode]
  if (!draft) {
    return
  }

  savingPlanCode.value = planCode
  pageError.value = null
  pageMessage.value = null

  try {
    await updateAdminPlan(planCode, {
      name: draft.name.trim(),
      monthly_story_limit: optionalNumber(draft.monthly_story_limit) ?? undefined,
      max_pages_per_story: optionalNumber(draft.max_pages_per_story) ?? undefined,
      image_quality_mode: optionalString(draft.image_quality_mode) ?? undefined,
      voice_clone_limit: optionalNumber(draft.voice_clone_limit) ?? undefined,
      monthly_audio_chars_limit: optionalNumber(draft.monthly_audio_chars_limit) ?? undefined,
      price_cents: optionalNumber(draft.price_cents) ?? 0,
      active: draft.active,
    })
    pageMessage.value = `Plan ${planCode} updated.`
    await Promise.allSettled([loadPlans(), reloadUserState()])
  } catch (error) {
    pageError.value = getErrorMessage(error)
  } finally {
    savingPlanCode.value = null
  }
}

watch(selectedUserId, async (userId) => {
  if (!userId) {
    selectedUser.value = null
    syncSelectedUserForms(null)
    return
  }

  await loadUserDetail(userId)
})

onMounted(async () => {
  await Promise.allSettled([loadPlans(), loadUsers()])
  if (selectedUserId.value) {
    await loadUserDetail(selectedUserId.value)
  }
})
</script>

<template>
  <main class="min-h-screen px-4 py-6 sm:px-6 sm:py-8">
    <div class="app-shell space-y-6">
      <div class="page-header">
        <div>
          <p class="page-kicker">Internal operations</p>
          <h1 class="page-title">Admin Console</h1>
          <p class="page-subtitle">
            Review subscriptions, effective usage limits, and per-user entitlement changes from one internal workspace.
          </p>
        </div>

        <div class="flex flex-wrap gap-3">
          <RouterLink :to="{ name: 'subscription' }" class="nav-link">Plan</RouterLink>
          <RouterLink :to="{ name: 'dashboard' }" class="nav-link">&larr; Dashboard</RouterLink>
        </div>
      </div>

      <div
        v-if="pageError"
        class="rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700"
        role="alert"
      >
        {{ pageError }}
      </div>

      <div
        v-if="pageMessage"
        class="rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700"
      >
        {{ pageMessage }}
      </div>

      <section class="surface-card space-y-4 px-6 py-6 sm:px-8">
        <div class="flex items-start justify-between gap-4">
          <div>
            <p class="page-kicker">Plans</p>
            <h2 class="mt-2 text-2xl font-semibold text-[var(--app-ink)]">Database-defined base limits</h2>
            <p class="mt-2 text-sm text-[var(--app-muted)]">
              Staff can inspect plan rows. Admins can edit these base limits directly.
            </p>
          </div>
          <p class="text-xs uppercase tracking-[0.22em] text-[var(--app-muted)]">
            {{ canEditPlans ? 'Admin editing enabled' : 'Read only for staff' }}
          </p>
        </div>

        <div v-if="isLoadingPlans && plans.length === 0" class="py-6 text-sm text-[var(--app-muted)]">
          Loading plans…
        </div>

        <div v-else class="grid gap-4 xl:grid-cols-2">
          <article
            v-for="plan in plans"
            :key="plan.code"
            class="rounded-[30px] border border-[var(--app-border)] bg-white/80 px-5 py-5"
          >
            <div class="flex items-start justify-between gap-3">
              <div>
                <p class="page-kicker">{{ plan.code }}</p>
                <h3 class="mt-2 text-xl font-semibold text-[var(--app-ink)]">{{ planDraft(plan).name }}</h3>
              </div>
              <span class="rounded-full bg-stone-100 px-3 py-1 text-xs uppercase tracking-[0.18em] text-[var(--app-muted)]">
                {{ planDraft(plan).active ? 'Active' : 'Inactive' }}
              </span>
            </div>

            <div class="mt-4 grid gap-3 sm:grid-cols-2">
              <label class="space-y-2 text-sm text-[var(--app-muted)]">
                <span>Display name</span>
                <input v-model="planDraft(plan).name" class="form-input" :disabled="!canEditPlans" type="text">
              </label>
              <label class="space-y-2 text-sm text-[var(--app-muted)]">
                <span>Price cents</span>
                <input v-model="planDraft(plan).price_cents" class="form-input" :disabled="!canEditPlans" type="number" min="0">
              </label>
              <label class="space-y-2 text-sm text-[var(--app-muted)]">
                <span>Stories / month</span>
                <input v-model="planDraft(plan).monthly_story_limit" class="form-input" :disabled="!canEditPlans" type="number" min="0">
              </label>
              <label class="space-y-2 text-sm text-[var(--app-muted)]">
                <span>Max pages / story</span>
                <input v-model="planDraft(plan).max_pages_per_story" class="form-input" :disabled="!canEditPlans" type="number" min="0">
              </label>
              <label class="space-y-2 text-sm text-[var(--app-muted)]">
                <span>Voice clones / month</span>
                <input v-model="planDraft(plan).voice_clone_limit" class="form-input" :disabled="!canEditPlans" type="number" min="0">
              </label>
              <label class="space-y-2 text-sm text-[var(--app-muted)]">
                <span>Narration chars / month</span>
                <input v-model="planDraft(plan).monthly_audio_chars_limit" class="form-input" :disabled="!canEditPlans" type="number" min="0">
              </label>
              <label class="space-y-2 text-sm text-[var(--app-muted)]">
                <span>Image quality mode</span>
                <input v-model="planDraft(plan).image_quality_mode" class="form-input" :disabled="!canEditPlans" type="text">
              </label>
              <label class="flex items-center gap-3 rounded-2xl border border-[var(--app-border)] px-4 py-3 text-sm text-[var(--app-muted)]">
                <input v-model="planDraft(plan).active" :disabled="!canEditPlans" type="checkbox">
                <span>Plan is active</span>
              </label>
            </div>

            <button
              v-if="canEditPlans"
              class="primary-button mt-5"
              type="button"
              :disabled="savingPlanCode === plan.code"
              @click="savePlan(plan.code)"
            >
              {{ savingPlanCode === plan.code ? 'Saving…' : 'Save plan' }}
            </button>
          </article>
        </div>
      </section>

      <section class="grid gap-5 lg:grid-cols-[0.95fr_1.25fr]">
        <aside class="surface-card space-y-4 px-6 py-6">
          <div class="flex items-start justify-between gap-3">
            <div>
              <p class="page-kicker">Users</p>
              <h2 class="mt-2 text-2xl font-semibold text-[var(--app-ink)]">Search accounts</h2>
            </div>
            <span class="text-xs uppercase tracking-[0.22em] text-[var(--app-muted)]">
              {{ users.length }} loaded
            </span>
          </div>

          <form class="flex gap-2" @submit.prevent="handleSearch">
            <input
              v-model="searchQuery"
              class="form-input flex-1"
              type="search"
              placeholder="Search by email or name"
            >
            <button class="secondary-button" type="submit" :disabled="isLoadingUsers">
              {{ isLoadingUsers ? 'Searching…' : 'Search' }}
            </button>
          </form>

          <div v-if="isLoadingUsers && users.length === 0" class="py-6 text-sm text-[var(--app-muted)]">
            Loading users…
          </div>

          <div v-else-if="users.length === 0" class="rounded-3xl border border-dashed border-[var(--app-border)] px-4 py-6 text-sm text-[var(--app-muted)]">
            No users matched the current search.
          </div>

          <div v-else class="space-y-3">
            <button
              v-for="user in users"
              :key="user.id"
              class="w-full rounded-[26px] border px-4 py-4 text-left transition"
              :class="selectedUserId === user.id ? 'border-[var(--app-accent-strong)] bg-[var(--app-accent-soft)]' : 'border-[var(--app-border)] bg-white/70'"
              type="button"
              @click="selectedUserId = user.id"
            >
              <div class="flex items-start justify-between gap-3">
                <div>
                  <p class="text-sm font-medium text-[var(--app-ink)]">{{ user.full_name || user.primary_email || user.id }}</p>
                  <p class="mt-1 text-xs uppercase tracking-[0.18em] text-[var(--app-muted)]">{{ user.primary_email || 'No email' }}</p>
                </div>
                <span class="rounded-full bg-stone-100 px-3 py-1 text-[11px] uppercase tracking-[0.18em] text-[var(--app-muted)]">
                  {{ user.role }}
                </span>
              </div>
              <p class="mt-3 text-sm text-[var(--app-muted)]">
                {{ user.plan.name }} · {{ user.usage.stories_created?.remaining ?? '∞' }} stories remaining
              </p>
            </button>
          </div>
        </aside>

        <section class="surface-card px-6 py-6 sm:px-7">
          <div v-if="isLoadingUserDetail && !selectedUser" class="py-10 text-sm text-[var(--app-muted)]">
            Loading user detail…
          </div>

          <div v-else-if="!selectedUser" class="py-10 text-sm text-[var(--app-muted)]">
            Select a user to inspect their subscription and entitlement state.
          </div>

          <div v-else class="space-y-6">
            <div class="flex flex-wrap items-start justify-between gap-4">
              <div>
                <p class="page-kicker">Selected user</p>
                <h2 class="mt-2 text-3xl font-semibold text-[var(--app-ink)]">
                  {{ selectedUser.full_name || selectedUser.primary_email || selectedUser.id }}
                </h2>
                <p class="mt-2 text-sm text-[var(--app-muted)]">
                  {{ selectedUser.primary_email || 'No primary email' }} · {{ selectedUser.plan.name }} ({{ selectedUser.plan.code }})
                </p>
              </div>
              <div class="rounded-[26px] border border-[var(--app-border)] bg-white/80 px-4 py-4 text-sm text-[var(--app-muted)]">
                <p>Current period</p>
                <p class="mt-2 font-medium text-[var(--app-ink)]">
                  {{ selectedUser.current_period_start ? new Date(selectedUser.current_period_start).toLocaleDateString() : 'Unknown start' }}
                  to
                  {{ selectedUser.current_period_end ? new Date(selectedUser.current_period_end).toLocaleDateString() : 'Open ended' }}
                </p>
              </div>
            </div>

            <div class="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
              <article
                v-for="(metric, usageType) in selectedUser.usage"
                :key="usageType"
                class="rounded-[26px] border border-[var(--app-border)] bg-white/80 px-4 py-4"
              >
                <p class="text-xs uppercase tracking-[0.22em] text-[var(--app-muted)]">{{ usageLabels[usageType] || usageType }}</p>
                <p class="mt-2 text-3xl font-semibold text-[var(--app-ink)]">{{ metric.used }}</p>
                <p class="mt-2 text-sm text-[var(--app-muted)]">
                  {{ metric.limit === null ? 'Unlimited base limit' : `${metric.remaining ?? 0} remaining of ${metric.limit}` }}
                </p>
              </article>
            </div>

            <div class="grid gap-4 xl:grid-cols-2">
              <form class="rounded-[30px] border border-[var(--app-border)] bg-white/75 px-5 py-5" @submit.prevent="assignPlan">
                <p class="page-kicker">Subscription</p>
                <h3 class="mt-2 text-xl font-semibold text-[var(--app-ink)]">Assign plan</h3>
                <label class="mt-4 block space-y-2 text-sm text-[var(--app-muted)]">
                  <span>Plan code</span>
                  <select v-model="subscriptionForm.plan_code" class="form-input">
                    <option v-for="plan in plans" :key="plan.code" :value="plan.code">{{ plan.code }}</option>
                  </select>
                </label>
                <button class="primary-button mt-4" type="submit" :disabled="isAssigningPlan">
                  {{ isAssigningPlan ? 'Updating…' : 'Assign subscription' }}
                </button>
              </form>

              <form class="rounded-[30px] border border-[var(--app-border)] bg-white/75 px-5 py-5" @submit.prevent="saveRole">
                <p class="page-kicker">Permissions</p>
                <h3 class="mt-2 text-xl font-semibold text-[var(--app-ink)]">User role</h3>
                <label class="mt-4 block space-y-2 text-sm text-[var(--app-muted)]">
                  <span>Role</span>
                  <select v-model="roleForm.role" class="form-input" :disabled="!canEditRoles">
                    <option value="customer">customer</option>
                    <option value="staff">staff</option>
                    <option value="admin">admin</option>
                  </select>
                </label>
                <button
                  v-if="canEditRoles"
                  class="secondary-button mt-4"
                  type="submit"
                  :disabled="isSavingRole"
                >
                  {{ isSavingRole ? 'Saving…' : 'Save role' }}
                </button>
                <p v-else class="mt-4 text-sm text-[var(--app-muted)]">Only admins can change user roles.</p>
              </form>
            </div>

            <div class="grid gap-4 xl:grid-cols-2">
              <form class="rounded-[30px] border border-[var(--app-border)] bg-white/75 px-5 py-5" @submit.prevent="saveOverride">
                <p class="page-kicker">Override</p>
                <h3 class="mt-2 text-xl font-semibold text-[var(--app-ink)]">Absolute entitlement override</h3>
                <div class="mt-4 grid gap-3 sm:grid-cols-2">
                  <input v-model="overrideForm.monthly_story_limit" class="form-input" type="number" min="0" placeholder="Stories / month">
                  <input v-model="overrideForm.max_pages_per_story" class="form-input" type="number" min="0" placeholder="Max pages / story">
                  <input v-model="overrideForm.voice_clone_limit" class="form-input" type="number" min="0" placeholder="Voice clones / month">
                  <input v-model="overrideForm.monthly_audio_chars_limit" class="form-input" type="number" min="0" placeholder="Narration chars / month">
                  <input v-model="overrideForm.image_quality_mode" class="form-input" type="text" placeholder="Image quality mode">
                  <input v-model="overrideForm.effective_to" class="form-input" type="datetime-local" placeholder="Expiry">
                </div>
                <textarea
                  v-model="overrideForm.reason"
                  class="form-input mt-3 min-h-[96px]"
                  placeholder="Reason for this override"
                />
                <button class="primary-button mt-4" type="submit" :disabled="isSavingOverride">
                  {{ isSavingOverride ? 'Saving…' : 'Create override' }}
                </button>
              </form>

              <form class="rounded-[30px] border border-[var(--app-border)] bg-white/75 px-5 py-5" @submit.prevent="saveGrant">
                <p class="page-kicker">Grant</p>
                <h3 class="mt-2 text-xl font-semibold text-[var(--app-ink)]">Add usage credit</h3>
                <div class="mt-4 grid gap-3 sm:grid-cols-2">
                  <select v-model="grantForm.usage_type" class="form-input">
                    <option value="stories_created">Stories</option>
                    <option value="voice_clones_created">Voice clones</option>
                    <option value="audio_chars_synthesized">Narration characters</option>
                  </select>
                  <input v-model="grantForm.quantity" class="form-input" type="number" min="1" placeholder="Quantity">
                  <input v-model="grantForm.effective_to" class="form-input sm:col-span-2" type="datetime-local" placeholder="Expiry">
                </div>
                <textarea
                  v-model="grantForm.reason"
                  class="form-input mt-3 min-h-[96px]"
                  placeholder="Reason for this grant"
                />
                <button class="primary-button mt-4" type="submit" :disabled="isSavingGrant">
                  {{ isSavingGrant ? 'Saving…' : 'Create grant' }}
                </button>
              </form>
            </div>

            <div class="grid gap-4 xl:grid-cols-2">
              <article class="rounded-[30px] border border-[var(--app-border)] bg-white/75 px-5 py-5">
                <p class="page-kicker">Active override</p>
                <template v-if="selectedUser.active_override">
                  <h3 class="mt-2 text-xl font-semibold text-[var(--app-ink)]">{{ selectedUser.active_override.reason }}</h3>
                  <p class="mt-3 text-sm text-[var(--app-muted)]">
                    Stories {{ selectedUser.active_override.monthly_story_limit ?? 'unchanged' }} ·
                    Pages {{ selectedUser.active_override.max_pages_per_story ?? 'unchanged' }} ·
                    Voice clones {{ selectedUser.active_override.voice_clone_limit ?? 'unchanged' }}
                  </p>
                  <button class="secondary-button mt-4" type="button" @click="revokeOverride(selectedUser.active_override.id)">
                    Revoke override
                  </button>
                </template>
                <p v-else class="mt-3 text-sm text-[var(--app-muted)]">No active override.</p>
              </article>

              <article class="rounded-[30px] border border-[var(--app-border)] bg-white/75 px-5 py-5">
                <p class="page-kicker">Active grants</p>
                <div v-if="selectedUser.active_grants.length > 0" class="mt-3 space-y-3">
                  <div
                    v-for="grant in selectedUser.active_grants"
                    :key="grant.id"
                    class="rounded-2xl border border-[var(--app-border)] px-4 py-4"
                  >
                    <p class="font-medium text-[var(--app-ink)]">{{ usageLabels[grant.usage_type] || grant.usage_type }} +{{ grant.quantity }}</p>
                    <p class="mt-1 text-sm text-[var(--app-muted)]">{{ grant.reason }}</p>
                    <button class="secondary-button mt-3" type="button" @click="revokeGrant(grant.id)">
                      Revoke grant
                    </button>
                  </div>
                </div>
                <p v-else class="mt-3 text-sm text-[var(--app-muted)]">No active usage grants.</p>
              </article>
            </div>

            <article class="rounded-[30px] border border-[var(--app-border)] bg-white/75 px-5 py-5">
              <p class="page-kicker">Audit trail</p>
              <div v-if="selectedUser.recent_audit_events.length > 0" class="mt-3 space-y-3">
                <div
                  v-for="event in selectedUser.recent_audit_events"
                  :key="event.id"
                  class="rounded-2xl border border-[var(--app-border)] px-4 py-4"
                >
                  <div class="flex flex-wrap items-center justify-between gap-3">
                    <p class="font-medium text-[var(--app-ink)]">{{ event.event_type }}</p>
                    <span class="text-xs uppercase tracking-[0.18em] text-[var(--app-muted)]">
                      {{ new Date(event.created_at).toLocaleString() }}
                    </span>
                  </div>
                  <p class="mt-2 text-sm text-[var(--app-muted)]">{{ event.entity_type }} · actor {{ event.actor_user_id || 'system' }}</p>
                </div>
              </div>
              <p v-else class="mt-3 text-sm text-[var(--app-muted)]">No audit events yet.</p>
            </article>
          </div>
        </section>
      </section>
    </div>
  </main>
</template>
