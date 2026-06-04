/**
 * countdown.js — Countdown event page.
 *
 * Features:
 *   - Live ticking display (days / hours / minutes / seconds) for each card
 *   - Expired-event handling (replaces countdown with a message)
 *   - Add / edit countdown modal
 *   - Delete countdown with optimistic DOM removal
 *
 * Dependencies: utils.js (apiPost, openModal, closeModal).
 */

'use strict';

// ── Live countdown ticker ─────────────────────────────────────────────────────

(function () {
  const cards = Array.from(document.querySelectorAll('.countdown-card[data-target]'));
  if (!cards.length) return;

  /**
   * Pre-cache per-card DOM references so the update loop never queries
   * the DOM inside the interval — one querySelector per card on init only.
   */
  const refs = cards.map((card) => ({
    card,
    targetMs:     new Date(card.dataset.target).getTime(),
    days:         card.querySelector('[data-unit="days"]'),
    hours:        card.querySelector('[data-unit="hours"]'),
    minutes:      card.querySelector('[data-unit="minutes"]'),
    seconds:      card.querySelector('[data-unit="seconds"]'),
    expiredShown: false,
  }));

  /** Update every card's countdown display. Called once per second. */
  function _updateAll() {
    const now = Date.now();

    refs.forEach((r) => {
      const diff = r.targetMs - now;

      if (diff <= 0) {
        // Show "event passed" message only once per card
        if (!r.expiredShown) {
          const unitsEl = r.card.querySelector('.cd-units');
          if (unitsEl) {
            unitsEl.innerHTML = '<div class="cd-expired">🎉 This event has passed!</div>';
          }
          r.expiredShown = true;
        }
        return;
      }

      const days    = Math.floor(diff / 86_400_000);
      const hours   = Math.floor((diff % 86_400_000) / 3_600_000);
      const minutes = Math.floor((diff % 3_600_000)  / 60_000);
      const seconds = Math.floor((diff % 60_000)      / 1_000);

      if (r.days)    r.days.textContent    = days;
      if (r.hours)   r.hours.textContent   = String(hours).padStart(2, '0');
      if (r.minutes) r.minutes.textContent = String(minutes).padStart(2, '0');
      if (r.seconds) r.seconds.textContent = String(seconds).padStart(2, '0');
    });
  }

  _updateAll();
  setInterval(_updateAll, 1000);
})();

// ── Modal state ───────────────────────────────────────────────────────────────

// Cache modal field refs once rather than querying on every open
const _cdModal      = document.getElementById('cdModal');
const _cdModalTitle = document.getElementById('cdModalTitle');
const _editCdId     = document.getElementById('editCdId');
const _cdTitleIn    = document.getElementById('cdTitle');
const _cdDateIn     = document.getElementById('cdDate');
const _cdEmojiIn    = document.getElementById('cdEmoji');

// ── Modal open/close helpers ──────────────────────────────────────────────────

/**
 * Open the modal in "add" mode with all fields cleared.
 */
function openAddCd() {
  if (!_cdModal) return;
  if (_cdModalTitle) _cdModalTitle.textContent = 'New Countdown';
  if (_editCdId)     _editCdId.value           = '';
  if (_cdTitleIn)    _cdTitleIn.value           = '';
  if (_cdDateIn)     _cdDateIn.value            = '';
  if (_cdEmojiIn)    _cdEmojiIn.value           = '🎯';
  openModal('cdModal');
  _cdTitleIn?.focus();
}

/**
 * Open the modal in "edit" mode, pre-populated with an existing countdown's values.
 *
 * @param {number} id    - Countdown ID.
 * @param {string} title - Current title.
 * @param {string} date  - Current target datetime (ISO).
 * @param {string} emoji - Current emoji.
 */
function openEditCd(id, title, date, emoji) {
  if (!_cdModal) return;
  if (_cdModalTitle) _cdModalTitle.textContent = 'Edit Countdown';
  if (_editCdId)     _editCdId.value           = id;
  if (_cdTitleIn)    _cdTitleIn.value           = title;
  // datetime-local input only accepts 'YYYY-MM-DDTHH:MM' (16 chars)
  if (_cdDateIn)     _cdDateIn.value            = date.slice(0, 16);
  if (_cdEmojiIn)    _cdEmojiIn.value           = emoji;
  openModal('cdModal');
  _cdTitleIn?.focus();
}

function closeCdModal() {
  closeModal('cdModal');
}

document.getElementById('openAddCd')?.addEventListener('click', openAddCd);

// ── Save countdown ─────────────────────────────────────────────────────────────

document.getElementById('saveCdBtn')?.addEventListener('click', async () => {
  const id    = _editCdId?.value || '';
  const title = _cdTitleIn?.value.trim();
  const date  = _cdDateIn?.value;
  const emoji = _cdEmojiIn?.value.trim() || '🎯';

  if (!title || title.length > 200) {
    alert('Please enter a valid event name (max 200 characters).');
    _cdTitleIn?.focus();
    return;
  }
  if (!date) {
    alert('Please select a target date.');
    _cdDateIn?.focus();
    return;
  }

  const url     = id ? `/countdown/${id}/edit` : '/countdown/add';
  const payload = { title, target_date: date, emoji };

  try {
    await apiPost(url, payload);
    location.reload();
  } catch (e) {
    alert(e.message || 'Failed to save countdown.');
  }
});

// ── Delete countdown ──────────────────────────────────────────────────────────

/**
 * Confirm and permanently delete a countdown card.
 * Removes the card from the DOM immediately and shows the empty state if needed.
 *
 * @param {number} id - Countdown ID.
 */
async function deleteCd(id) {
  if (!confirm('Delete this countdown?')) return;

  try {
    await apiPost(`/countdown/${id}/delete`);
    document.querySelector(`.countdown-card[data-id="${id}"]`)?.remove();

    // Show the empty state when no cards remain
    if (!document.querySelectorAll('.countdown-card').length) {
      const grid = document.getElementById('countdownGrid');
      if (grid) {
        grid.innerHTML = `
          <div class="empty-state" id="emptyCd" style="grid-column:1/-1">
            <i class="fa-solid fa-hourglass-half" aria-hidden="true"></i>
            <p>No countdowns yet. Add an upcoming event!</p>
          </div>`;
      }
    }
  } catch (e) {
    alert(e.message || 'Failed to delete countdown.');
  }
}
