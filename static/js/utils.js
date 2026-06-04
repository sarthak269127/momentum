/**
 * utils.js — Shared utilities loaded on every page.
 *
 * Provides:
 *   - getCsrf()         — read the CSRF token from the page meta tag
 *   - apiPost(url, data) — authenticated JSON POST wrapper
 *   - apiGet(url)        — JSON GET wrapper
 *   - fmtSeconds(s)      — format a second count as HH:MM:SS or MM:SS
 *   - todayISO()         — today's date as YYYY-MM-DD
 *   - tomorrowISO()      — tomorrow's date as YYYY-MM-DD
 *   - nextWeekISO()      — date 7 days from now as YYYY-MM-DD
 *   - openModal(id)      — show a modal overlay by element ID
 *   - closeModal(id)     — hide a modal overlay by element ID
 *   - UI helpers         — profile dropdown, mobile sidebar, flash dismiss
 *
 * Load order: this file must be loaded BEFORE any page-specific script
 * that calls apiPost, apiGet, or the modal helpers.
 */

'use strict';

// ── CSRF ──────────────────────────────────────────────────────────────────────

/**
 * Read the CSRF token injected into the page by the Flask template.
 * The token is stored in <meta name="csrf-token"> to be accessible to JS
 * without embedding it in every form or AJAX payload.
 *
 * @returns {string} The CSRF token, or an empty string if not found.
 */
function getCsrf() {
  return document.querySelector('meta[name="csrf-token"]')?.content || '';
}

// ── API wrappers ───────────────────────────────────────────────────────────────

/**
 * Send a CSRF-protected JSON POST request and return the parsed response.
 *
 * Automatically attaches the X-CSRFToken header so every mutating request
 * is protected without callers needing to handle CSRF manually.
 *
 * @param {string} url   - Relative URL of the endpoint.
 * @param {object} [data={}] - Request body (will be JSON-serialised).
 * @returns {Promise<object>} Parsed JSON response body.
 * @throws {Error} On non-2xx responses, with message from { error } field or
 *                 "HTTP <status>" fallback.
 */
async function apiPost(url, data = {}) {
  const response = await fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRFToken': getCsrf(),
    },
    body: JSON.stringify(data),
  });

  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.error || `HTTP ${response.status}`);
  }

  return response.json();
}

/**
 * Send a JSON GET request and return the parsed response.
 *
 * @param {string} url - Relative URL of the endpoint.
 * @returns {Promise<object>} Parsed JSON response body.
 * @throws {Error} On non-2xx responses.
 */
async function apiGet(url) {
  const response = await fetch(url);
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  return response.json();
}

// ── Time formatting ────────────────────────────────────────────────────────────

/**
 * Format a raw second count into a human-readable timer string.
 *
 * Omits the hours component when the value is under one hour.
 * Examples:  90   → "01:30"
 *            3661 → "1:01:01"
 *
 * @param {number} s - Total seconds (non-negative integer).
 * @returns {string} Formatted time string.
 */
function fmtSeconds(s) {
  s = Math.max(0, Math.floor(s));
  const hours   = Math.floor(s / 3600);
  const minutes = Math.floor((s % 3600) / 60);
  const seconds = s % 60;

  if (hours > 0) {
    return `${hours}:${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
  }
  return `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
}

// ── Date helpers ───────────────────────────────────────────────────────────────

/**
 * Return today's date as an ISO string (YYYY-MM-DD).
 * Uses local time, not UTC, to match the user's calendar day.
 *
 * @returns {string}
 */
function todayISO() {
  return new Date().toISOString().split('T')[0];
}

/**
 * Return tomorrow's date as an ISO string (YYYY-MM-DD).
 *
 * @returns {string}
 */
function tomorrowISO() {
  const d = new Date();
  d.setDate(d.getDate() + 1);
  return d.toISOString().split('T')[0];
}

/**
 * Return the date 7 days from now as an ISO string (YYYY-MM-DD).
 *
 * @returns {string}
 */
function nextWeekISO() {
  const d = new Date();
  d.setDate(d.getDate() + 7);
  return d.toISOString().split('T')[0];
}

// ── Modal helpers ──────────────────────────────────────────────────────────────

/**
 * Show a modal overlay by adding the 'active' class.
 *
 * @param {string} id - The element ID of the .modal-overlay element.
 */
function openModal(id) {
  document.getElementById(id)?.classList.add('active');
}

/**
 * Hide a modal overlay by removing the 'active' class.
 *
 * @param {string} id - The element ID of the .modal-overlay element.
 */
function closeModal(id) {
  document.getElementById(id)?.classList.remove('active');
}

// Close modal when the user clicks the overlay background (not the box inside)
document.addEventListener('click', (e) => {
  if (e.target.classList.contains('modal-overlay')) {
    e.target.classList.remove('active');
  }
});

// Close any open modal when the user presses Escape
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') {
    document.querySelectorAll('.modal-overlay.active')
      .forEach((m) => m.classList.remove('active'));
  }
});

// ── Flash message auto-dismiss ─────────────────────────────────────────────────

// Auto-fade flash banners after 4 seconds so they don't linger forever
setTimeout(() => {
  document.querySelectorAll('.flash').forEach((el) => {
    el.style.transition = 'opacity 0.4s';
    el.style.opacity    = '0';
    setTimeout(() => el.remove(), 400);
  });
}, 4000);

// ── Profile dropdown ──────────────────────────────────────────────────────────

const _profileBtn  = document.getElementById('profileBtn');
const _profileDrop = _profileBtn?.closest('.profile-dropdown');

if (_profileBtn && _profileDrop) {
  _profileBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    const isOpen = _profileDrop.classList.toggle('open');
    // Update ARIA state for screen readers
    _profileBtn.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
  });

  // Close dropdown when the user clicks anywhere outside it
  document.addEventListener('click', () => {
    _profileDrop.classList.remove('open');
    _profileBtn.setAttribute('aria-expanded', 'false');
  });
}

// ── Mobile sidebar toggle ─────────────────────────────────────────────────────

const _menuBtn         = document.getElementById('menuBtn');
const _sidebar         = document.querySelector('.sidebar');
const _sidebarOverlay  = document.getElementById('sidebarOverlay');

function openSidebar() {
  _sidebar?.classList.add('open');
  _sidebarOverlay?.classList.add('active');
  document.body.style.overflow = 'hidden'; // prevent background scroll
  _menuBtn?.setAttribute('aria-expanded', 'true');
}

function closeSidebar() {
  _sidebar?.classList.remove('open');
  _sidebarOverlay?.classList.remove('active');
  document.body.style.overflow = '';
  _menuBtn?.setAttribute('aria-expanded', 'false');
}

_menuBtn?.addEventListener('click', openSidebar);
_sidebarOverlay?.addEventListener('click', closeSidebar);

// Auto-close sidebar when a nav link is tapped on mobile
document.querySelectorAll('.nav a').forEach((link) => {
  link.addEventListener('click', () => {
    if (window.innerWidth <= 768) closeSidebar();
  });
});
