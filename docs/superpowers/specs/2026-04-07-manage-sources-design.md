# Manage Sources — Design Spec

**Date:** 2026-04-07  
**Status:** Approved

---

## Overview

Add a "Manage Sources" modal that lets users view existing scraper sources, test whether their selectors still work, edit them if broken, and delete them.

---

## Architecture

### Files changed

| File | Change |
|------|--------|
| `frontend/src/components/ManageSources.vue` | New — source list modal |
| `frontend/src/components/ScraperTool.vue` | Add optional `editSite` prop for edit mode |
| `frontend/src/stores/scraper.ts` | Add `deleteSite(id)` action |
| `frontend/src/views/HomeView.vue` | Add "Manage Sources" button |

No backend changes required. All needed endpoints already exist:
- `GET /scraper/sites` — list sources
- `POST /scraper/test` — test chapter selectors
- `POST /scraper/sites` — upsert site (used for both add and edit)
- `DELETE /scraper/sites/:id` — delete site

---

## ManageSources.vue

A modal opened by a "Manage Sources" button in `HomeView`.

### On open
Calls `fetchSites()` to load the current source list.

### Source row layout
Each row displays:
- Site name + truncated URL
- Status badge (idle / testing / pass / fail)
- **Test** button
- **Edit** button
- **Delete** button

### Status badge states
| State | Appearance |
|-------|-----------|
| Idle | `—` grey |
| Testing | spinner |
| Pass | `✓ Pass` green |
| Fail | `✗ Fail` red |

Clicking a pass or fail badge opens a small popup anchored to the badge containing:
- Match counts: titles matched, chapter links matched, covers matched
- Up to 4 preview cards (cover thumbnail, title, chapter number)

Test result state is stored as local component state keyed by site ID — ephemeral, not persisted to the store.

### Test action
Calls `POST /scraper/test` with the site's saved URL and selectors. Updates the badge on completion.

### Edit action
Closes `ManageSources`, opens `ScraperTool` with the `editSite` prop set to the selected source.

### Delete action
Replaces the delete button inline with "Sure?" + confirm/cancel. On confirm, calls `DELETE /scraper/sites/:id` and refreshes the list. No separate dialog.

### Empty state
If no sources exist, shows a short message hinting the user to add one.

---

## ScraperTool.vue — Edit Mode

### Prop
```ts
editSite?: ScraperSite  // optional; when set, activates edit mode
```

### Edit mode behaviour
- Modal title: "Edit Source"
- Starts at the `selectors` step (URL step skipped)
- All selector fields pre-filled from `editSite`
- URL field is read-only with a visual indicator
- Step counter shows 3 steps (selectors → test → done)
- Save calls the existing `saveSite` action — no backend change needed (upserts by URL)

---

## Store additions (`scraper.ts`)

```ts
async function deleteSite(id: number): Promise<void> {
  await api.delete(`/scraper/sites/${id}`)
  await fetchSites()
}
```

---

## Error handling

- Test fetch failure: badge shows `✗ Fail`; popup shows the error message
- Delete failure: inline error message on the row
- Edit save failure: handled by existing ScraperTool error handling
