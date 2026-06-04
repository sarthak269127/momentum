/**
 * notes.js — Notes list page.
 *
 * Handles:
 *   - Creating a new blank note and navigating to its editor
 *   - Removing a note from the list without a full page reload
 *
 * Dependencies: utils.js (apiPost, todayISO).
 */

'use strict';

// ── Create note ───────────────────────────────────────────────────────────────

/**
 * Create a new empty note on the server, then navigate to its editor page.
 * The user starts typing immediately on the dedicated note-detail page.
 */
document.getElementById('openAddNote')?.addEventListener('click', async () => {
  try {
    const note = await apiPost('/notes/create', { title: '', content: '' });
    window.location.href = `/notes/${note.id}`;
  } catch (e) {
    alert(e.message || 'Failed to create note.');
  }
});

// ── Delete note from list ─────────────────────────────────────────────────────

/**
 * Confirm and delete a note card from the list.
 * Any linked reminder task is intentionally preserved.
 *
 * @param {Event}  e  - Click event (stopped so the card's navigate-click won't fire).
 * @param {number} id - Note ID.
 */
async function deleteNote(e, id) {
  e.stopPropagation();
  e.preventDefault();

  if (!confirm('Delete this note? Any linked reminder task will remain.')) return;

  try {
    await apiPost(`/notes/${id}/delete`, { delete_task: false });
    document.querySelector(`.note-card[data-id="${id}"]`)?.remove();
    _checkEmpty();
  } catch (err) {
    alert(err.message || 'Failed to delete note.');
  }
}

/**
 * Show the empty-state placeholder when the last note card is removed.
 */
function _checkEmpty() {
  const grid  = document.getElementById('notesGrid');
  const cards = grid?.querySelectorAll('.note-card');
  const empty = document.getElementById('emptyNotes');
  if (empty) empty.style.display = cards?.length ? 'none' : '';
}
