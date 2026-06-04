/**
 * dashboard.js — Dashboard page.
 *
 * Handles:
 *   - Quick-toggle task completion from the dashboard task list
 *   - Weekly focus bar chart (Chart.js, data injected by template)
 *
 * Dependencies:
 *   utils.js (apiPost) must load first.
 *   Chart.js is loaded via CDN in the template's {% block head %}.
 *   window.WEEKLY_FOCUS is injected by the template before this script.
 */

'use strict';

// ── Quick-toggle tasks ────────────────────────────────────────────────────────

/**
 * Attach click handlers to all dashboard task-check circles.
 * Toggles the completed state in-place without a page reload.
 */
document.querySelectorAll('.dash-task-check').forEach((checkEl) => {
  checkEl.addEventListener('click', async function () {
    const item = this.closest('.dash-task-item');
    const id   = item?.dataset.id;
    if (!id) return;

    try {
      const res = await apiPost(`/tasks/toggle/${id}`);

      this.classList.toggle('done', res.completed);
      this.innerHTML = res.completed
        ? '<i class="fa-solid fa-check" aria-hidden="true"></i>'
        : '';

      const titleEl = item.querySelector('.dash-task-title');
      if (titleEl) titleEl.classList.toggle('done', res.completed);
    } catch (e) {
      console.error('[dashboard] Toggle failed:', e);
    }
  });
});

// ── Weekly focus chart ────────────────────────────────────────────────────────

/**
 * Render the weekly focus bar chart if Chart.js and the data are available.
 * window.WEEKLY_FOCUS is an array of { day: string, minutes: number }.
 */
if (window.WEEKLY_FOCUS && document.getElementById('weeklyChart')) {
  const ctx = document.getElementById('weeklyChart').getContext('2d');

  new Chart(ctx, {
    type: 'bar',
    data: {
      labels: window.WEEKLY_FOCUS.map((d) => d.day),
      datasets: [{
        data:            window.WEEKLY_FOCUS.map((d) => d.minutes),
        backgroundColor: 'rgba(91, 92, 255, 0.65)',
        borderRadius:    6,
        borderSkipped:   false,
      }],
    },
    options: {
      plugins: { legend: { display: false } },
      scales: {
        x: {
          grid:  { color: 'rgba(255, 255, 255, 0.05)' },
          ticks: { color: '#94a3b8' },
        },
        y: {
          grid:       { color: 'rgba(255, 255, 255, 0.05)' },
          ticks:      { color: '#94a3b8' },
          beginAtZero: true,
        },
      },
    },
  });
}
