/**
 * tasks.js — Tasks page logic.
 *
 * Responsibilities:
 *   - Add / edit task modal (open, populate, save)
 *   - Date-chip shortcuts (Today / Tomorrow / Next Week)
 *   - Toggle task completion in-place
 *   - Delete task in-place
 *   - Client-side filter tabs (All / Today / Upcoming / Overdue / Active / Completed)
 *   - Task summary bar (total, pending, done, overdue counts)
 *
 * Dependencies:
 *   utils.js must be loaded first for apiPost, apiGet, openModal,
 *   closeModal, todayISO, tomorrowISO, nextWeekISO.
 */

'use strict';

// ── Date constants (sourced from shared utils to avoid duplication) ────────────
const TODAY_ISO    = todayISO();
const TOMORROW_ISO = tomorrowISO();
const NEXTWEEK_ISO = nextWeekISO();

// ── Add / Edit Task Modal ──────────────────────────────────────────────────────

/**
 * Open the task modal in "add" mode with default field values.
 * Sets the due date chip to "Today" by default.
 */
function openAddTaskModal() {
  _setModalHeading('New Task');
  _clearModalFields();
  document.getElementById('newTaskDate').value = TODAY_ISO;
  _setActiveChip('today');
  openModal('addTaskModal');
  document.getElementById('newTaskTitle')?.focus();
}

/**
 * Open the task modal in "edit" mode, pre-populated with an existing task's values.
 *
 * @param {number} id       - Task ID.
 * @param {string} title    - Current task title.
 * @param {string} date     - Current due date (YYYY-MM-DD).
 * @param {string} priority - Current priority level.
 * @param {string} [desc]   - Current description (optional).
 */
function openEditTask(id, title, date, priority, desc) {
  _setModalHeading('Edit Task');
  document.getElementById('editTaskId').value       = id;
  document.getElementById('newTaskTitle').value      = title;
  document.getElementById('newTaskDate').value       = date;
  document.getElementById('newTaskPriority').value   = priority;
  document.getElementById('newTaskDesc').value       = desc || '';
  // Clear all chips — the date picker shows the exact stored date
  document.querySelectorAll('.date-chip').forEach((c) => c.classList.remove('active'));
  openModal('addTaskModal');
  document.getElementById('newTaskTitle')?.focus();
}

function closeAddModal() {
  closeModal('addTaskModal');
}

// ── Private modal helpers ──────────────────────────────────────────────────────

function _setModalHeading(text) {
  const el = document.getElementById('modalHeading');
  if (el) el.textContent = text;
}

function _clearModalFields() {
  document.getElementById('editTaskId').value      = '';
  document.getElementById('newTaskTitle').value    = '';
  document.getElementById('newTaskDate').value     = '';
  document.getElementById('newTaskPriority').value = 'medium';
  document.getElementById('newTaskDesc').value     = '';
}

function _setActiveChip(chipName) {
  document.querySelectorAll('.date-chip').forEach((c) => c.classList.remove('active'));
  document.querySelector(`[data-chip="${chipName}"]`)?.classList.add('active');
}

// ── Event listeners ────────────────────────────────────────────────────────────

document.getElementById('openAddTask')?.addEventListener('click', openAddTaskModal);

// Date chip shortcuts set the date input and mark themselves active
document.querySelectorAll('.date-chip').forEach((chip) => {
  chip.addEventListener('click', () => {
    document.querySelectorAll('.date-chip').forEach((c) => c.classList.remove('active'));
    chip.classList.add('active');

    const dateMap = {
      'today':     TODAY_ISO,
      'tomorrow':  TOMORROW_ISO,
      'next-week': NEXTWEEK_ISO,
    };
    const value = dateMap[chip.dataset.chip];
    if (value) document.getElementById('newTaskDate').value = value;
  });
});

// Manually typing a date deactivates all chips
document.getElementById('newTaskDate')?.addEventListener('change', () => {
  document.querySelectorAll('.date-chip').forEach((c) => c.classList.remove('active'));
});

// ── Save (add or edit) ────────────────────────────────────────────────────────

document.getElementById('saveTaskBtn')?.addEventListener('click', async () => {
  const id    = document.getElementById('editTaskId').value;
  const title = document.getElementById('newTaskTitle').value.trim();
  const date  = document.getElementById('newTaskDate').value;
  const prio  = document.getElementById('newTaskPriority').value;
  const desc  = document.getElementById('newTaskDesc').value.trim();

  if (!title || title.length > 200) {
    alert('Please enter a valid task title (max 200 characters).');
    document.getElementById('newTaskTitle')?.focus();
    return;
  }
  if (!date) {
    alert('Please select a due date.');
    return;
  }

  const url     = id ? `/tasks/edit/${id}` : '/tasks/add';
  const payload = { title, task_date: date, priority: prio, description: desc };

  try {
    await apiPost(url, payload);
    location.reload();
  } catch (e) {
    alert(e.message || 'Failed to save task.');
  }
});

// ── Toggle complete ────────────────────────────────────────────────────────────

/**
 * Toggle a task row's completed state and update the summary bar.
 *
 * @param {HTMLElement} row - The .tasks-row element.
 */
async function toggleTask(row) {
  const id = row.dataset.id;
  try {
    const res = await apiPost(`/tasks/toggle/${id}`);
    row.dataset.done = res.completed ? 'true' : 'false';
    row.classList.toggle('done', res.completed);
    updateSummary();
  } catch (e) {
    alert(e.message || 'Failed to toggle task.');
  }
}

// ── Delete ────────────────────────────────────────────────────────────────────

/**
 * Confirm and delete a task row, then refresh the summary.
 *
 * @param {Event}  e  - Click event (stopped from bubbling to the row's edit handler).
 * @param {number} id - Task ID.
 */
async function deleteTask(e, id) {
  e.stopPropagation();
  if (!confirm('Delete this task?')) return;
  try {
    await apiPost(`/tasks/delete/${id}`);
    document.querySelector(`.tasks-row[data-id="${id}"]`)?.remove();
    updateSummary();
    _checkEmpty();
  } catch (e) {
    alert(e.message || 'Failed to delete task.');
  }
}

// ── Filter tabs ───────────────────────────────────────────────────────────────

document.querySelectorAll('.filter-tab').forEach((tab) => {
  tab.addEventListener('click', () => {
    document.querySelectorAll('.filter-tab').forEach((t) => t.classList.remove('active'));
    tab.classList.add('active');
    _applyFilter(tab.dataset.filter);
  });
});

/**
 * Show/hide task rows and date-group headers based on the selected filter.
 *
 * @param {string} filter - One of: 'all'|'today'|'upcoming'|'overdue'|'active'|'completed'
 */
function _applyFilter(filter) {
  document.querySelectorAll('.tasks-row').forEach((row) => {
    const due  = row.dataset.due;
    const done = row.dataset.done === 'true';
    let show = true;

    switch (filter) {
      case 'today':     show = due === TODAY_ISO; break;
      case 'upcoming':  show = due > TODAY_ISO; break;
      case 'overdue':   show = due < TODAY_ISO && !done; break;
      case 'active':    show = !done; break;
      case 'completed': show = done; break;
      // 'all' — default, show everything
    }

    row.style.display = show ? '' : 'none';
  });

  // Hide date-group headers whose rows are all invisible
  document.querySelectorAll('.tasks-date-group').forEach((group) => {
    let sibling = group.nextElementSibling;
    let anyVisible = false;
    while (sibling && sibling.classList.contains('tasks-row')) {
      if (sibling.style.display !== 'none') anyVisible = true;
      sibling = sibling.nextElementSibling;
    }
    group.style.display = anyVisible ? '' : 'none';
  });
}

// ── Summary bar ───────────────────────────────────────────────────────────────

/**
 * Recalculate and render the task summary bar (total / pending / done / overdue).
 * Called after every toggle or delete.
 */
function updateSummary() {
  const rows    = Array.from(document.querySelectorAll('.tasks-row'));
  const total   = rows.length;
  const done    = rows.filter((r) => r.dataset.done === 'true').length;
  const pending = total - done;
  const overdue = rows.filter((r) => r.dataset.due < TODAY_ISO && r.dataset.done !== 'true').length;

  const summary = document.getElementById('tasksSummary');
  if (!summary) return;

  const parts = [
    `${total} total`,
    `${pending} pending`,
    `${done} done`,
    overdue > 0 ? `${overdue} overdue` : null,
  ].filter(Boolean);

  summary.innerHTML = parts.map((p) => `<span>${p}</span>`).join(' · ');
}

/**
 * Show the empty-state placeholder when the task list becomes empty.
 */
function _checkEmpty() {
  const rows    = document.querySelectorAll('.tasks-row');
  const emptyEl = document.getElementById('emptyMsg');
  if (emptyEl) emptyEl.style.display = rows.length ? 'none' : '';
}

// ── Initialise ────────────────────────────────────────────────────────────────
updateSummary();
