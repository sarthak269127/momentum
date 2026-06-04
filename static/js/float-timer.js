/**
 * float-timer.js — Floating timer widget (present on every page).
 *
 * SESSION MODEL (mirrors timer.js rules):
 *
 *   The floating widget ONLY:
 *     - Starts / pauses / resumes the timer
 *     - Displays current time
 *     - Handles Reset (which triggers the one allowed stopwatch save)
 *
 *   It does NOT save sessions on pause or resume.
 *
 *   STOPWATCH reset: saves total elapsed to backend.
 *   TIMER completion: handled entirely by timer.js on the timer page.
 *     If a timer completes while only the floating widget is visible,
 *     the completed flag is set in localStorage and handled on next
 *     visit to the timer page (or by the completion check below).
 *
 * MULTI-TAB:
 *   Float widget uses its own FLOAT_TAB_ID.
 *   Only one owner can run at a time.
 *   storage event keeps display in sync across all tabs.
 */

'use strict';

(function () {
  const LS_STATE     = 'momentum_timer_state';
  const LS_COLLAPSED = 'momentum_float_collapsed';
  const FLOAT_TAB_ID = 'float_' + Math.random().toString(36).slice(2);

  // ── DOM refs ────────────────────────────────────────────────────────────────
  const display     = document.getElementById('floatDisplay');
  const playIcon    = document.getElementById('floatPlayIcon');
  const labelEl     = document.getElementById('floatLabel');
  const body        = document.getElementById('floatTimerBody');
  const chevron     = document.getElementById('floatChevron');
  const collapseBtn = document.getElementById('floatCollapseBtn');
  const playBtn     = document.getElementById('floatPlayBtn');
  const resetBtn    = document.getElementById('floatResetBtn');

  if (!display) return;

  // ── fmt helper (utils.js loads first; fallback just in case) ────────────────
  function fmt(s) {
    if (typeof fmtSeconds === 'function') return fmtSeconds(s);
    s = Math.max(0, Math.floor(s));
    const m = Math.floor(s / 60), sec = s % 60;
    return `${String(m).padStart(2,'0')}:${String(sec).padStart(2,'0')}`;
  }

  // ── Store helpers ────────────────────────────────────────────────────────────
  function loadState() {
    try { return JSON.parse(localStorage.getItem(LS_STATE)) || {}; } catch { return {}; }
  }
  function saveState(s) {
    localStorage.setItem(LS_STATE, JSON.stringify(s));
  }
  function applyDefaults(s) {
    if (!s.mode)                    s.mode         = 'timer';
    if (!s.totalSeconds)            s.totalSeconds = 25 * 60;
    if (s.running    === undefined) s.running      = false;
    if (s.remaining  === undefined) s.remaining    = s.totalSeconds;
    if (s.elapsed    === undefined) s.elapsed      = 0;
    if (s.startedAt  === undefined) s.startedAt    = null;
    if (s.completed  === undefined) s.completed    = false;
    if (s.tabId      === undefined) s.tabId        = null;
    return s;
  }

  // ── Live value derivation (startedAt never mutated during display) ──────────
  function liveElapsed(s) {
    const base = s.elapsed || 0;
    if (s.running && s.startedAt) return base + Math.floor((Date.now() - s.startedAt) / 1000);
    return base;
  }
  function liveRemaining(s) {
    const total = s.totalSeconds || 25 * 60;
    const base  = (s.remaining !== undefined) ? s.remaining : total;
    if (s.running && s.startedAt) return Math.max(0, base - Math.floor((Date.now() - s.startedAt) / 1000));
    return Math.max(0, base);
  }

  // ── Collapse ─────────────────────────────────────────────────────────────────
  let collapsed = localStorage.getItem(LS_COLLAPSED) === '1';
  function applyCollapse() {
    if (body)    body.style.display = collapsed ? 'none' : '';
    if (chevron) chevron.className  = collapsed ? 'fa-solid fa-chevron-up' : 'fa-solid fa-chevron-down';
    localStorage.setItem(LS_COLLAPSED, collapsed ? '1' : '0');
  }
  applyCollapse();
  collapseBtn?.addEventListener('click', (e) => {
    e.stopPropagation();
    collapsed = !collapsed;
    applyCollapse();
  });

  // ── Display update ───────────────────────────────────────────────────────────
  // Pure read + render — no state mutation inside the interval.
  function updateDisplay() {
    const s    = applyDefaults(loadState());
    const mode = s.mode;

    if (labelEl) labelEl.textContent = mode === 'stopwatch' ? 'Stopwatch' : 'Timer';

    if (mode === 'stopwatch') {
      display.textContent = fmt(liveElapsed(s));
    } else {
      display.textContent = fmt(liveRemaining(s));
    }

    if (playIcon) playIcon.className = s.running ? 'fa-solid fa-pause' : 'fa-solid fa-play';
  }

  // Single interval — never doubled
  updateDisplay();
  setInterval(updateDisplay, 1000);

  // ── saveSession helper ────────────────────────────────────────────────────────
  // Returns true on success, false on failure.
  // ONLY called from Reset (stopwatch) — never from pause.
  async function saveSession(duration, mode, completed) {
    if (duration < 10) return false;
    try {
      const res = await apiPost('/timer/save', { duration, mode, completed });
      return !!res;
    } catch (e) {
      console.warn('[float-timer] saveSession failed:', e);
      return false;
    }
  }

  // ── Play / Pause ──────────────────────────────────────────────────────────────
  // NO backend save. Pure state toggle.
  playBtn?.addEventListener('click', () => {
    const s = applyDefaults(loadState());

    if (s.running) {
      // ── PAUSE ──
      // Snapshot live value into persisted base
      if (s.mode === 'stopwatch') {
        s.elapsed = liveElapsed(s);
      } else {
        s.remaining = liveRemaining(s);
      }
      s.running   = false;
      s.startedAt = null;
      s.tabId     = null;
      saveState(s);
      // ✗ No backend save on pause

    } else {
      // ── RESUME / START ──
      // Don't steal ownership from an active timer page tab
      if (s.running) return; // already running (race condition guard)
      s.running   = true;
      s.startedAt = Date.now(); // set once on start, never mutated
      s.completed = false;
      s.tabId     = FLOAT_TAB_ID;
      saveState(s);
    }

    updateDisplay();
  });

  // ── Reset ─────────────────────────────────────────────────────────────────────
  // STOPWATCH: save total elapsed, then zero.
  // TIMER: discard (no save — timer must reach 00:00 naturally for a save).
  resetBtn?.addEventListener('click', async () => {
    const s    = applyDefaults(loadState());
    const mode = s.mode;

    if (mode === 'stopwatch') {
      const total = liveElapsed(s);

      s.elapsed   = 0;
      s.running   = false;
      s.startedAt = null;
      s.completed = false;
      s.tabId     = null;
      saveState(s);
      updateDisplay();

      // One save on reset — stats update only if this succeeds
      await saveSession(total, 'stopwatch', false);

    } else {
      // Timer reset — discard
      s.remaining = s.totalSeconds || 25 * 60;
      s.running   = false;
      s.startedAt = null;
      s.completed = false;
      s.tabId     = null;
      saveState(s);
      updateDisplay();
    }
  });

  // ── Multi-tab sync ────────────────────────────────────────────────────────────
  // Float widget is display-only re: sync — it just re-renders.
  window.addEventListener('storage', (e) => {
    if (e.key === LS_STATE) updateDisplay();
  });

})();
