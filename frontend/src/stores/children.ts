import { ref } from 'vue'
import { defineStore } from 'pinia'

import {
  getChildren as fetchChildrenApi,
  createChild as createChildApi,
  updateChild as updateChildApi,
  deleteChild as deleteChildApi,
  type Child,
  type CreateChildPayload,
  type UpdateChildPayload,
} from '@/services/children'

export const useChildrenStore = defineStore('children', () => {
  const children = ref<Child[]>([])
  const isLoading = ref(false)
  const error = ref<string | null>(null)

  async function fetchChildren() {
    isLoading.value = true
    error.value = null

    try {
      children.value = await fetchChildrenApi()
    } catch (e) {
      error.value = 'Failed to load children.'
      throw e
    } finally {
      isLoading.value = false
    }
  }

  async function createChild(payload: CreateChildPayload) {
    isLoading.value = true
    error.value = null

    try {
      const child = await createChildApi(payload)
      children.value.push(child)
      return child
    } catch (e) {
      error.value = 'Failed to create child profile.'
      throw e
    } finally {
      isLoading.value = false
    }
  }

  async function updateChild(childId: string, payload: UpdateChildPayload) {
    isLoading.value = true
    error.value = null

    try {
      const updated = await updateChildApi(childId, payload)
      const idx = children.value.findIndex((c) => c.id === childId)
      if (idx !== -1) {
        children.value[idx] = updated
      }
      return updated
    } catch (e) {
      error.value = 'Failed to update child profile.'
      throw e
    } finally {
      isLoading.value = false
    }
  }

  async function deleteChild(childId: string) {
    isLoading.value = true
    error.value = null

    try {
      await deleteChildApi(childId)
      children.value = children.value.filter((c) => c.id !== childId)
    } catch (e) {
      error.value = 'Failed to delete child profile.'
      throw e
    } finally {
      isLoading.value = false
    }
  }

  return {
    children,
    isLoading,
    error,
    fetchChildren,
    createChild,
    updateChild,
    deleteChild,
  }
})
