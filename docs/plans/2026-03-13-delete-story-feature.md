# Delete Story Feature — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Allow users to delete any story (READY, GENERATING, or FAILED) via a three-dot menu on story cards that opens a confirmation modal.

**Architecture:** Soft-delete (status → DELETED). Workers already check page/story status before writing, so deleting a GENERATING story is safe. Frontend uses a reusable `DeleteStoryModal` component with warning text and a destructive confirm button. Three-dot dropdown menu on each story card.

**Tech Stack:** FastAPI backend, Vue 3 + Tailwind frontend, Pinia store

---

## Completed

### Task 1: Backend — Remove FAILED-only guard
**File:** `backend/app/services/story.py:161-174`
**Status:** DONE

Removed the `if story.status != StoryStatus.FAILED` check. Any story status can now be deleted.

### Task 2: Backend tests — Update delete tests
**File:** `backend/tests/test_stories.py`
**Status:** DONE

- Replaced `test_delete_story_rejects_non_failed_status` (which expected 409) with:
  - `test_delete_ready_story_success` — deletes READY story, asserts 204 + 404 on detail
  - `test_delete_generating_story_success` — deletes GENERATING story, asserts 204 + 404 on detail
- Backend tests NOT YET RUN to verify.

### Task 3: Frontend — DeleteStoryModal component
**File:** `frontend/src/components/DeleteStoryModal.vue`
**Status:** DONE (file created)

Props: `storyTitle`, `storyStatus`, `isDeleting`. Emits: `confirm`, `cancel`.
Features:
- Warning icon + destructive red "Delete story" button
- Shows story title in the message
- Extra amber warning for GENERATING stories
- Teleported to body, transition-ready

---

## Remaining Tasks

### Task 4: Add modal/overlay CSS to main.css
**File:** `frontend/src/assets/main.css`

Add after the lightbox styles (around line 569):

```css
/* Modal overlay + panel */
.modal-overlay {
  position: fixed;
  inset: 0;
  z-index: 50;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(36, 29, 23, 0.5);
  backdrop-filter: blur(8px);
}

.modal-panel {
  background: var(--app-surface-strong);
  border-radius: 1.75rem;
  padding: 1.75rem;
  max-width: 26rem;
  width: calc(100% - 2rem);
  box-shadow: 0 24px 80px -20px rgba(0, 0, 0, 0.3);
}

/* Modal transitions */
.modal-enter-active {
  transition: opacity 200ms ease;
}
.modal-leave-active {
  transition: opacity 150ms ease;
}
.modal-enter-from,
.modal-leave-to {
  opacity: 0;
}
```

### Task 5: Add three-dot menu + modal to DashboardView
**File:** `frontend/src/views/DashboardView.vue`

Changes needed:
1. Import `DeleteStoryModal` and add `ref` state: `deleteTarget` (the story to delete), `isDeleting`
2. Replace the old `handleDeleteStory` (which used `window.confirm`) with:
   - `openDeleteModal(story)` — sets `deleteTarget`
   - `confirmDelete()` — calls `storiesStore.deleteStory()`, clears `deleteTarget`
   - `cancelDelete()` — clears `deleteTarget`
3. Replace the old inline delete button (lines 232-241, only showed for failed) with a three-dot menu button on ALL story cards:
   ```html
   <!-- Three-dot menu (top-right of card, next to status pill) -->
   <button @click.stop="openDeleteModal(story)" class="..." aria-label="Story options">
     <!-- Three dot SVG icon -->
   </button>
   ```
4. Add `<DeleteStoryModal>` at the bottom of template, conditionally rendered when `deleteTarget` is set.

### Task 6: Add delete option to StoryDetailView
**File:** `frontend/src/views/StoryDetailView.vue`

Changes needed:
1. Import `DeleteStoryModal`, add `deleteModalOpen` ref and `isDeleting` ref
2. Replace old `handleDeleteStory()` (line 181-187, uses `window.confirm`) with modal flow
3. Replace old inline delete button (lines 490-497, only showed for failed+no pages) with a delete button in the header metadata area that works for ANY status
4. Add `<DeleteStoryModal>` at the bottom of template

### Task 7: Update frontend tests
**File:** `frontend/src/views/__tests__/story-views.test.ts`

Two tests need updating:
- `deletes a failed story from the dashboard after confirmation` (line 271) — should now find the three-dot menu button, click it, then find "Delete story" in the modal and click it. Remove `window.confirm` expectation.
- `deletes a failed story from the detail view and returns to dashboard` (line 309) — same modal flow instead of `window.confirm`.

Consider adding a test for deleting a READY story from the dashboard.

### Task 8: Run all tests
```bash
cd backend && uv run pytest -v
cd frontend && npm run test:unit -- --run
```

---

## Design Decisions
- **Soft-delete only** — status set to DELETED, filtered from queries. No hard delete.
- **R2 asset cleanup deferred** — orphaned files remain in storage. Can add a cleanup job later.
- **Workers are safe** — they re-load story/page status before writing results, so deleting a GENERATING story won't cause crashes.
- **Three-dot menu** — keeps cards clean, provides a place for future actions (share, duplicate).
- **Confirmation modal** — warm editorial style, extra warning for generating stories.
