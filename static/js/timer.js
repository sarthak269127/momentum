/**
 * timer.js — Focus Timer & Stopwatch
 *
 * SESSION MODEL (new rules):
 *
 *   STOPWATCH:
 *     - Start / pause / resume freely — NO backend saves during any of these.
 *     - RESET: save ONE session for total elapsed time, then zero the counter.
 *
 *   TIMER:
 *     - Start / pause / resume freely — NO backend saves during any of these.
 *     - Natural completion (reaches 00:00): save ONE completed session.
 *     - Manual reset before completion: discard — nothing saved.
 *
 * STATE SHAPE (localStorage key: momentum_timer_state):
 * {
 *   mode:        'timer' | 'stopwatch'
 *   running:     boolean
 *   totalSeconds: number   — timer: full configured duration
 *   remaining:   number    — timer: seconds left when last paused/started
 *   elapsed:     number    — stopwatch: total seconds accumulated (pauses included)
 *   startedAt:   number|null — ms wall-clock when current run segment began
 *   completed:   boolean   — true once a timer session has been saved; blocks re-save
 *   tabId:       string|null — owner tab ID; other tabs yield to this
 * }
 *
 * ANTI-DUPLICATION:
 *   state.completed prevents onTimerFinished() from saving more than once,
 *   even if restore() fires in multiple tabs simultaneously.
 *
 * MODE-SWITCH PROTECTION:
 *   Blocked whenever ANY session is in progress (running OR paused with time on the clock).
 *   User must Reset first.
 *
 * MULTI-TAB:
 *   tabId ownership — only one tab runs the interval at a time.
 *   storage event keeps all tabs' displays in sync.
 */

'use strict';

// ── Guard: abort on non-timer pages ──────────────────────────────────────────
if (!document.getElementById('pomoTime')) {
  throw new Error('timer.js: not on timer page');
}

// ── Constants ─────────────────────────────────────────────────────────────────
const LS_STATE  = 'momentum_timer_state';
const TAB_ID    = Math.random().toString(36).slice(2);
const FULL_DASH = 2 * Math.PI * 96;

// ── fmtSeconds fallback (utils.js loads first but guard defensively) ──────────
if (typeof fmtSeconds !== 'function') {
  window.fmtSeconds = function (s) {
    s = Math.max(0, Math.floor(s));
    const h = Math.floor(s / 3600);
    const m = Math.floor((s % 3600) / 60);
    const sec = s % 60;
    if (h > 0) return `${h}:${String(m).padStart(2,'0')}:${String(sec).padStart(2,'0')}`;
    return `${String(m).padStart(2,'0')}:${String(sec).padStart(2,'0')}`;
  };
}

// ── Store ─────────────────────────────────────────────────────────────────────
const Store = {
  load() {
    try { return JSON.parse(localStorage.getItem(LS_STATE)) || {}; } catch { return {}; }
  },
  save(s) {
    localStorage.setItem(LS_STATE, JSON.stringify(s));
  },
  defaults(s) {
    if (!s.mode)                    s.mode         = 'timer';
    if (!s.totalSeconds)            s.totalSeconds = 25 * 60;
    if (s.running    === undefined) s.running      = false;
    if (s.remaining  === undefined) s.remaining    = s.totalSeconds;
    if (s.elapsed    === undefined) s.elapsed      = 0;
    if (s.startedAt  === undefined) s.startedAt    = null;
    if (s.completed  === undefined) s.completed    = false;
    if (s.tabId      === undefined) s.tabId        = null;
    return s;
  },
};

// ── DOM refs ──────────────────────────────────────────────────────────────────
const timeEl        = document.getElementById('pomoTime');
const statusEl      = document.getElementById('pomoStatus');
const playIcon      = document.getElementById('playIcon');
const ring          = document.getElementById('ringProgress');
const svgEl         = document.querySelector('.pomo-ring');
const timerInputRow = document.getElementById('timerInputRow');
const sessionsEl    = document.getElementById('sessionsCount');
const focusTodayEl  = document.getElementById('focusToday');

// Initialise focus stats from server (not 0)
let focusSecs = window._timerFocusSecs || 0;
let sessions  = parseInt(sessionsEl?.textContent) || 0;

// ── SVG ring setup ────────────────────────────────────────────────────────────
(function ensureGradient() {
  if (!svgEl) return;
  let defs = svgEl.querySelector('defs');
  if (!defs) {
    defs = document.createElementNS('http://www.w3.org/2000/svg', 'defs');
    svgEl.prepend(defs);
  }
  if (!defs.querySelector('#timerGrad')) {
    defs.innerHTML = `
      <linearGradient id="timerGrad" x1="0%" y1="0%" x2="100%" y2="0%">
        <stop offset="0%"   stop-color="#5b5cff"/>
        <stop offset="100%" stop-color="#7c5cff"/>
      </linearGradient>`;
  }
})();

if (ring) {
  ring.style.strokeDasharray  = FULL_DASH;
  ring.style.strokeDashoffset = 0;
}

// ── Live state ────────────────────────────────────────────────────────────────
let state    = Store.defaults(Store.load());
let interval = null;

// Derive current live values from persisted base + wall-clock delta.
// startedAt is set once on resume and never mutated during ticking.
function liveElapsed() {
  const base = state.elapsed || 0;
  if (state.running && state.startedAt) {
    return base + Math.floor((Date.now() - state.startedAt) / 1000);
  }
  return base;
}

function liveRemaining() {
  const base = (state.remaining !== undefined) ? state.remaining : state.totalSeconds;
  if (state.running && state.startedAt) {
    return Math.max(0, base - Math.floor((Date.now() - state.startedAt) / 1000));
  }
  return Math.max(0, base);
}

// ── Helpers: does a session currently exist that blocks mode switching? ───────
function sessionInProgress() {
  if (state.mode === 'stopwatch') return liveElapsed() > 0;
  return liveRemaining() < state.totalSeconds; // any time has been consumed
}

// ── Render ────────────────────────────────────────────────────────────────────
function render() {
  if (state.mode === 'stopwatch') {
    timeEl.textContent = fmtSeconds(liveElapsed());
    if (ring) ring.style.strokeDashoffset = 0;
  } else {
    const rem = liveRemaining();
    timeEl.textContent = fmtSeconds(rem);
    if (ring) {
      const pct = state.totalSeconds > 0 ? rem / state.totalSeconds : 1;
      ring.style.strokeDashoffset = FULL_DASH * (1 - pct);
    }
  }
}

function updateFocusDisplay() {
  if (focusTodayEl) focusTodayEl.textContent = Math.floor(focusSecs / 60) + 'm';
}

function setStatus(text, color) {
  if (!statusEl) return;
  statusEl.textContent = text;
  statusEl.style.color = color || '';
}

// ── Interval ──────────────────────────────────────────────────────────────────
function startInterval() {
  clearInterval(interval); // never allow two
  interval = setInterval(tick, 1000);
}

function stopInterval() {
  clearInterval(interval);
  interval = null;
}

function tick() {
  // Yield to another tab that took ownership
  const fresh = Store.load();
  if (fresh.tabId && fresh.tabId !== TAB_ID && fresh.running) {
    stopInterval();
    state = Store.defaults(fresh);
    render();
    return;
  }

  render();

  // Check natural timer completion
  if (state.mode === 'timer' && liveRemaining() <= 0) {
    onTimerFinished();
  }
}

// ── Session save ──────────────────────────────────────────────────────────────
// Returns true on success, false on any failure.
// focusSecs and sessions count ONLY update on confirmed success.
async function saveSession(duration, mode, completed) {
  if (duration < 10) return false;
  try {
    const res = await apiPost('/timer/save', { duration, mode, completed });
    if (!res) return false;
    // Confirmed: now update client-side stats
    focusSecs += duration;
    updateFocusDisplay();
    if (completed) {
      sessions++;
      if (sessionsEl) sessionsEl.textContent = sessions;
    }
    return true;
  } catch (e) {
    console.warn('[timer] saveSession failed:', e);
    return false;
  }
}

// ── Timer natural completion ───────────────────────────────────────────────────
// Called when timer reaches 00:00.
// state.completed prevents duplicate saves across tabs/restores.
async function onTimerFinished() {
  // Anti-duplication: check fresh state before doing anything
  const fresh = Store.load();
  if (fresh.completed) {
    // Already processed by another tab or a previous restore — just reset display
    stopInterval();
    state = Store.defaults(fresh);
    state.running   = false;
    state.startedAt = null;
    state.remaining = state.totalSeconds;
    Store.save(state);
    render();
    setStatus('🎉 Session complete!');
    return;
  }

  stopInterval();

  const duration = state.totalSeconds; // full configured duration

  // Mark completed in state FIRST so other tabs can't also fire
  state.running   = false;
  state.startedAt = null;
  state.remaining = state.totalSeconds;
  state.completed = true; // duplication guard
  state.tabId     = null;
  Store.save(state);

  setStatus('🎉 Session complete!');
  if (playIcon) playIcon.className = 'fa-solid fa-play';

  // Save to backend — stats only update if save succeeds
  await saveSession(duration, 'timer', true);

  render();
}

// ── Restore on page load ──────────────────────────────────────────────────────
function restore() {
  state = Store.defaults(Store.load());

  // If timer expired while away and hasn't been processed yet
  if (state.mode === 'timer' && !state.completed) {
    if (state.running && state.startedAt) {
      const elapsed = Math.floor((Date.now() - state.startedAt) / 1000);
      const wouldRemain = (state.remaining || state.totalSeconds) - elapsed;
      if (wouldRemain <= 0) {
        onTimerFinished();
        return;
      }
    } else if (!state.running && state.remaining <= 0) {
      // Paused exactly at 0 (edge case)
      onTimerFinished();
      return;
    }
  }

  // Restore mode UI
  if (state.mode === 'stopwatch') {
    if (timerInputRow) timerInputRow.style.display = 'none';
    document.getElementById('modeStopwatchBtn')?.classList.add('active');
    document.getElementById('modeTimerBtn')?.classList.remove('active');
    setStatus(state.running ? 'Counting up…' : (liveElapsed() > 0 ? 'Paused' : 'Ready to start'));
  } else {
    const durInput = document.getElementById('timerMinutes');
    if (durInput) durInput.value = Math.round(state.totalSeconds / 60);
    if (timerInputRow) timerInputRow.style.display = '';
    document.getElementById('modeTimerBtn')?.classList.add('active');
    document.getElementById('modeStopwatchBtn')?.classList.remove('active');
    if (state.completed) {
      setStatus('🎉 Session complete!');
    } else {
      setStatus(state.running ? 'Focus time!' : (liveRemaining() < state.totalSeconds ? 'Paused' : 'Ready to start'));
    }
  }

  render();

  if (state.running) {
    if (playIcon) playIcon.className = 'fa-solid fa-pause';
    state.tabId = TAB_ID; // claim ownership
    Store.save(state);
    startInterval();
  } else {
    if (playIcon) playIcon.className = 'fa-solid fa-play';
  }
}

// ── Play / Pause ──────────────────────────────────────────────────────────────
// NO backend save here. Pure state toggle.
document.getElementById('pomoBtnPlay')?.addEventListener('click', () => {
  if (state.running) {
    // ── PAUSE ──
    stopInterval();

    // Snapshot live value into persisted base
    if (state.mode === 'stopwatch') {
      state.elapsed = liveElapsed();
    } else {
      state.remaining = liveRemaining();
    }

    state.running   = false;
    state.startedAt = null;
    state.tabId     = null;
    Store.save(state);

    if (playIcon) playIcon.className = 'fa-solid fa-play';
    setStatus('Paused');

    // ✗ No backend save on pause

  } else {
    // ── RESUME / START ──
    state.running   = true;
    state.startedAt = Date.now(); // set once, never touched during ticking
    state.completed = false;      // clear completion guard on fresh start
    state.tabId     = TAB_ID;
    Store.save(state);

    if (playIcon) playIcon.className = 'fa-solid fa-pause';
    setStatus(state.mode === 'stopwatch' ? 'Counting up…' : 'Focus time!');
    startInterval();
  }
});

// ── Reset ─────────────────────────────────────────────────────────────────────
// STOPWATCH: saves total elapsed time to backend, then zeros.
// TIMER: discards — nothing saved (timer must reach 00:00 for a save).
document.getElementById('pomoBtnReset')?.addEventListener('click', async () => {
  stopInterval();

  if (state.mode === 'stopwatch') {
    const total = liveElapsed();

    // Snapshot before zeroing
    state.elapsed   = 0;
    state.running   = false;
    state.startedAt = null;
    state.completed = false;
    state.tabId     = null;
    Store.save(state);

    if (playIcon) playIcon.className = 'fa-solid fa-play';
    setStatus('Ready to start');
    render();

    // Save the full stopwatch session (one save, on reset)
    await saveSession(total, 'stopwatch', false);

  } else {
    // Timer reset — discard, no save
    state.remaining = state.totalSeconds;
    state.running   = false;
    state.startedAt = null;
    state.completed = false;
    state.tabId     = null;
    Store.save(state);

    if (playIcon) playIcon.className = 'fa-solid fa-play';
    setStatus('Ready to start');
    render();
  }
});

// ── Set Duration ──────────────────────────────────────────────────────────────
document.getElementById('setTimerBtn')?.addEventListener('click', () => {
  const input = document.getElementById('timerMinutes');
  const mins  = Math.max(1, parseInt(input?.value) || 25);
  if (input) input.value = mins;

  stopInterval();
  state.totalSeconds = mins * 60;
  state.remaining    = state.totalSeconds;
  state.running      = false;
  state.startedAt    = null;
  state.completed    = false;
  state.tabId        = null;
  Store.save(state);

  if (playIcon) playIcon.className = 'fa-solid fa-play';
  setStatus('Ready to start');
  render();
});

// ── Mode switch ───────────────────────────────────────────────────────────────
// Blocked if ANY session is in progress (running OR paused with time on clock).
// User must Reset first.
function switchMode(mode) {
  if (state.mode === mode) return;

  if (sessionInProgress()) {
    setStatus('⚠ Reset the current session before switching modes.', '#f87171');
    setTimeout(() => {
      setStatus(state.running
        ? (state.mode === 'stopwatch' ? 'Counting up…' : 'Focus time!')
        : 'Paused');
      if (statusEl) statusEl.style.color = '';
    }, 2500);
    return;
  }

  stopInterval();

  state.mode      = mode;
  state.running   = false;
  state.startedAt = null;
  state.elapsed   = 0;
  state.remaining = state.totalSeconds;
  state.completed = false;
  state.tabId     = null;
  Store.save(state);

  if (playIcon) playIcon.className = 'fa-solid fa-play';
  setStatus('Ready to start');
  if (statusEl) statusEl.style.color = '';

  if (mode === 'stopwatch') {
    if (timerInputRow) timerInputRow.style.display = 'none';
    document.getElementById('modeStopwatchBtn')?.classList.add('active');
    document.getElementById('modeTimerBtn')?.classList.remove('active');
  } else {
    const mins = parseInt(document.getElementById('timerMinutes')?.value) || 25;
    state.totalSeconds = mins * 60;
    state.remaining    = state.totalSeconds;
    Store.save(state);
    if (timerInputRow) timerInputRow.style.display = '';
    document.getElementById('modeTimerBtn')?.classList.add('active');
    document.getElementById('modeStopwatchBtn')?.classList.remove('active');
  }

  render();
}

document.getElementById('modeTimerBtn')?.addEventListener('click',      () => switchMode('timer'));
document.getElementById('modeStopwatchBtn')?.addEventListener('click',  () => switchMode('stopwatch'));

// ── Multi-tab storage sync ────────────────────────────────────────────────────
window.addEventListener('storage', (e) => {
  if (e.key !== LS_STATE) return;
  const fresh = Store.defaults(Store.load());
  // Yield interval if another tab took ownership
  if (fresh.running && fresh.tabId && fresh.tabId !== TAB_ID && interval) {
    stopInterval();
    if (playIcon) playIcon.className = 'fa-solid fa-play';
    setStatus('Running in another tab');
  }
  state = fresh;
  render();
});

// ── Init ──────────────────────────────────────────────────────────────────────
restore();
