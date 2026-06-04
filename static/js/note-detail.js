/**
 * note-detail.js — Note editor page.
 *
 * Features:
 *   - Autosave with 1.5 s debounce on every keypress
 *   - Visual save status indicator (Saved / Saving… / Unsaved / Error)
 *   - Optional reminder datetime with browser Notification API scheduling
 *   - Test notification button
 *   - Delete note with optional co-deletion of linked reminder task
 *
 * Dependencies: utils.js (apiPost, openModal, closeModal).
 * The NOTE_ID global is injected by the template before this script loads.
 */

'use strict';

(function () {
  // Guard: NOTE_ID must be set by the template
  const NOTE_ID = window.NOTE_ID;
  if (!NOTE_ID) return;

  // ── DOM refs ───────────────────────────────────────────────────────────────
  const indicator      = document.getElementById('autosaveIndicator');
  const titleInput     = document.getElementById('noteTitle');
  const contentArea    = document.getElementById('noteContent');
  const hasReminderCb  = document.getElementById('hasReminder');
  const reminderDtWrap = document.getElementById('reminderDtWrap');
  const reminderDtIn   = document.getElementById('reminderDatetime');

  // ── Autosave state ─────────────────────────────────────────────────────────
  let saveTimer = null;
  let isDirty   = false;

  // ── Save-status indicator ──────────────────────────────────────────────────

  /** Map of state names to icon+label HTML snippets. */
  const STATUS_ICONS = {
    saved:   '<i class="fa-solid fa-cloud-check" aria-hidden="true"></i> Saved',
    saving:  '<i class="fa-solid fa-spinner fa-spin" aria-hidden="true"></i> Saving…',
    unsaved: '<i class="fa-solid fa-clock" aria-hidden="true"></i> Unsaved',
    error:   '<i class="fa-solid fa-circle-exclamation" aria-hidden="true"></i> Error',
  };

  /**
   * Update the autosave indicator to reflect the current state.
   *
   * @param {'saved'|'saving'|'unsaved'|'error'} state
   */
  function setStatus(state) {
    if (!indicator) return;
    indicator.innerHTML = STATUS_ICONS[state] ?? STATUS_ICONS.saved;
    indicator.dataset.state = state;
  }

  /**
   * Mark the note as modified and schedule an autosave in 1.5 seconds.
   * Resets the timer if the user keeps typing.
   */
  function markDirty() {
    isDirty = true;
    setStatus('unsaved');
    clearTimeout(saveTimer);
    saveTimer = setTimeout(saveNote, 1500);
  }

  // ── Save ───────────────────────────────────────────────────────────────────

  /**
   * Persist the current note content to the server.
   *
   * Called automatically by the autosave timer or on beforeunload.
   * On success, schedules a browser notification if a reminder is set.
   */
  async function saveNote() {
    if (!isDirty) return;
    setStatus('saving');
    isDirty = false;

    const title             = titleInput?.value || '';
    const content           = contentArea?.value || '';
    const has_reminder      = hasReminderCb?.checked || false;
    const reminder_datetime = (has_reminder && reminderDtIn?.value) ? reminderDtIn.value : null;

    try {
      await apiPost(`/notes/${NOTE_ID}/save`, {
        title,
        content,
        has_reminder,
        reminder_datetime,
      });
      setStatus('saved');

      // Schedule a browser notification if a reminder was just set
      if (has_reminder && reminder_datetime) {
        _scheduleNotification(title || 'Note reminder', reminder_datetime);
      }
    } catch (e) {
      console.error('[note-detail] Save failed:', e);
      setStatus('error');
      isDirty = true; // Allow a retry on next edit
    }
  }

  // ── Browser notifications ──────────────────────────────────────────────────

  const LS_REMINDERS = 'momentum_note_reminders';

  /** Load the stored reminders map from localStorage. */
  function _loadReminders() {
    try { return JSON.parse(localStorage.getItem(LS_REMINDERS)) || {}; }
    catch { return {}; }
  }

  /** Persist the reminders map to localStorage. */
  function _persistReminders(reminders) {
    localStorage.setItem(LS_REMINDERS, JSON.stringify(reminders));
  }

  /**
   * Store a reminder entry so the periodic check can fire it at the right time.
   *
   * @param {string} title       - Notification title text.
   * @param {string} datetimeStr - ISO datetime string for when to fire.
   */
  function _scheduleNotification(title, datetimeStr) {
    const reminders = _loadReminders();
    reminders[NOTE_ID] = { title, datetime: datetimeStr };
    _persistReminders(reminders);

    // Request permission proactively if not yet decided
    if (Notification?.permission === 'default') {
      Notification.requestPermission();
    }
  }

  /**
   * Fire any stored reminders whose time has passed in the last 60 seconds.
   * Removes fired reminders from localStorage so they only trigger once.
   * Called every 30 seconds.
   */
  function _checkDueReminders() {
    if (Notification?.permission !== 'granted') return;
    const reminders = _loadReminders();
    const now       = Date.now();
    let changed     = false;

    for (const [id, rem] of Object.entries(reminders)) {
      const triggerMs = new Date(rem.datetime).getTime();
      // Fire if the trigger time is within the past 60-second window
      if (triggerMs <= now && triggerMs > now - 60_000) {
        new Notification('📝 Note Reminder', {
          body: rem.title || 'You have a note reminder',
          tag:  `note-reminder-${id}`,
        });
        delete reminders[id];
        changed = true;
      }
    }

    if (changed) _persistReminders(reminders);
  }

  setInterval(_checkDueReminders, 30_000);
  _checkDueReminders(); // Check immediately on page load

  // ── Reminder toggle ────────────────────────────────────────────────────────

  hasReminderCb?.addEventListener('change', function () {
    if (reminderDtWrap) reminderDtWrap.style.display = this.checked ? '' : 'none';
    // Request permission when the user first enables reminders
    if (this.checked && Notification?.permission === 'default') {
      Notification.requestPermission();
    }
    markDirty();
  });

  reminderDtIn?.addEventListener('change', markDirty);

  // ── Test notification ──────────────────────────────────────────────────────

  document.getElementById('testNotifBtn')?.addEventListener('click', () => {
    if (!window.Notification) {
      alert('Browser notifications are not supported in this browser.');
      return;
    }
    if (Notification.permission === 'denied') {
      alert('Notifications are blocked. Enable them in your browser settings.');
      return;
    }
    Notification.requestPermission().then((perm) => {
      if (perm === 'granted') {
        new Notification('📝 Test Reminder', {
          body: titleInput?.value || 'This is a test reminder',
          tag:  'test-reminder',
        });
      } else {
        alert('Notification permission was not granted.');
      }
    });
  });

  // ── Input event listeners ──────────────────────────────────────────────────

  titleInput?.addEventListener('input',  markDirty);
  contentArea?.addEventListener('input', markDirty);

  // Flush any unsaved changes when the user navigates away
  window.addEventListener('beforeunload', () => {
    if (isDirty) saveNote();
  });

  // ── Delete note ────────────────────────────────────────────────────────────

  document.getElementById('deleteNoteBtn')?.addEventListener('click', () => {
    openModal('deleteNoteModal');
  });

  document.getElementById('confirmDeleteNote')?.addEventListener('click', async () => {
    const deleteLinkedTask = document.getElementById('deleteTaskToo')?.checked || false;
    try {
      await apiPost(`/notes/${NOTE_ID}/delete`, { delete_task: deleteLinkedTask });
      window.location.href = '/notes/';
    } catch (e) {
      alert(e.message || 'Failed to delete note.');
    }
  });
})();
