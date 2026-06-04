/**
 * habits.js — Habits page logic.
 *
 * Responsibilities:
 *   - Filter tabs (All / Due Today / Daily / Interval / Weekdays)
 *   - Toggle habit completion for today
 *   - Delete habit with confirmation
 *   - Add habit modal (frequency selection, weekday picker, color swatches)
 *
 * Dependencies:
 *   utils.js must be loaded first for apiPost, openModal, closeModal.
 */

'use strict';

// Today's date injected by the template so habit toggles use the server's
// notion of "today" rather than the browser's clock (avoids timezone edge cases).
const HABITS_TODAY = window.HABITS_TODAY || todayISO();

// ── Filter tabs ───────────────────────────────────────────────────────────────

document.querySelectorAll('[data-hfilter]').forEach((btn) => {
  btn.addEventListener('click', function () {
    document.querySelectorAll('[data-hfilter]').forEach((b) => b.classList.remove('active'));
    this.classList.add('active');

    const filter = this.dataset.hfilter;
    document.querySelectorAll('.habit-card').forEach((card) => {
      let visible = true;
      if      (filter === 'today') visible = card.dataset.due === 'true';
      else if (filter !== 'all')   visible = card.dataset.freq === filter;
      card.style.display = visible ? '' : 'none';
    });
  });
});

// ── Toggle habit completion ───────────────────────────────────────────────────

/**
 * Toggle today's completion for a habit and update its card's UI.
 *
 * @param {HTMLButtonElement} btn - The check-in button that was clicked.
 * @param {number}            id  - Habit ID.
 */
async function toggleHabitToday(btn, id) {
  try {
    const data = await apiPost(`/habits/${id}/toggle`, { date: HABITS_TODAY });
    const card = btn.closest('.habit-card');

    btn.classList.toggle('done', data.done);
    btn.innerHTML = data.done
      ? '<i class="fa-solid fa-circle-check" aria-hidden="true"></i> Done today!'
      : '<i class="fa-solid fa-circle" aria-hidden="true"></i> Mark as done';

    // Update streak and rate counters on the card without a full reload
    const streakEl = card.querySelector('.habit-streak');
    const rateEl   = card.querySelector('.habit-rate');
    if (streakEl) streakEl.textContent = data.streak;
    if (rateEl)   rateEl.textContent   = `${data.rate}%`;
  } catch (e) {
    alert(e.message || 'Failed to toggle habit.');
  }
}

// ── Delete habit ──────────────────────────────────────────────────────────────

/**
 * Confirm and permanently delete a habit and all its history.
 *
 * @param {Event}  e  - Click event (stopped from bubbling to card).
 * @param {number} id - Habit ID.
 */
async function deleteHabit(e, id) {
  e.stopPropagation();
  if (!confirm('Delete this habit and all its history? This cannot be undone.')) return;

  try {
    await apiPost(`/habits/${id}/delete`);
    document.querySelector(`.habit-card[data-id="${id}"]`)?.remove();
    _checkEmpty();
  } catch (e) {
    alert(e.message || 'Failed to delete habit.');
  }
}

/**
 * Show the empty-state placeholder when all habit cards have been removed.
 */
function _checkEmpty() {
  const grid  = document.querySelector('.habits-grid');
  const cards = grid?.querySelectorAll('.habit-card');
  const empty = document.getElementById('emptyHabits');
  if (empty) empty.style.display = cards?.length ? 'none' : '';
}

// ── Add habit modal ────────────────────────────────────────────────────────────

document.getElementById('openAddHabit')?.addEventListener('click', () => {
  // Reset all modal fields before opening
  document.getElementById('habitName').value  = '';
  document.getElementById('habitColor').value = '#5b6ef5';
  document.getElementById('habitIcon').value  = 'fa-solid fa-star';

  document.querySelectorAll('.freq-tab').forEach((t) => t.classList.remove('active'));
  document.querySelector('[data-freq="daily"]')?.classList.add('active');

  document.getElementById('weekdayPicker').style.display  = 'none';
  document.getElementById('intervalPicker').style.display = 'none';
  document.querySelectorAll('.wd-btn').forEach((b) => b.classList.remove('active'));

  _curFreq = 'daily';
  openModal('habitModal');
  document.getElementById('habitName')?.focus();
});

// ── Frequency selector ────────────────────────────────────────────────────────

/** Currently selected frequency type — kept in module scope. */
let _curFreq = 'daily';

document.querySelectorAll('.freq-tab').forEach((tab) => {
  tab.addEventListener('click', function () {
    document.querySelectorAll('.freq-tab').forEach((t) => t.classList.remove('active'));
    this.classList.add('active');
    _curFreq = this.dataset.freq;

    // Show/hide conditional pickers based on selected frequency
    document.getElementById('weekdayPicker').style.display  = _curFreq === 'weekdays' ? '' : 'none';
    document.getElementById('intervalPicker').style.display = _curFreq === 'interval'  ? '' : 'none';
  });
});

// Individual weekday toggle buttons
document.querySelectorAll('.wd-btn').forEach((btn) => {
  btn.addEventListener('click', () => btn.classList.toggle('active'));
});

// ── Color swatches ────────────────────────────────────────────────────────────

document.querySelectorAll('.color-swatch').forEach((swatch) => {
  swatch.addEventListener('click', () => {
    document.querySelectorAll('.color-swatch').forEach((s) => s.classList.remove('active'));
    swatch.classList.add('active');
    const colorInput = document.getElementById('habitColor');
    if (colorInput) colorInput.value = swatch.dataset.color;
  });
});

// ── Save new habit ────────────────────────────────────────────────────────────

document.getElementById('saveHabit')?.addEventListener('click', async () => {
  const name = document.getElementById('habitName')?.value.trim();

  if (!name || name.length > 100) {
    alert('Please enter a habit name (max 100 characters).');
    document.getElementById('habitName')?.focus();
    return;
  }

  // Collect active weekday buttons as a comma-separated string of ints
  const weekdays = [...document.querySelectorAll('.wd-btn.active')]
    .map((b) => b.dataset.day)
    .join(',');

  const interval_days = _curFreq === 'interval'
    ? (parseInt(document.getElementById('intervalDays')?.value, 10) || null)
    : null;

  const payload = {
    name,
    frequency_type: _curFreq,
    weekdays,
    interval_days,
    color: document.getElementById('habitColor')?.value || '#5b6ef5',
    icon:  document.getElementById('habitIcon')?.value  || 'fa-solid fa-star',
  };

  try {
    await apiPost('/habits/add', payload);
    location.reload();
  } catch (e) {
    alert(e.message || 'Failed to save habit.');
  }
});
