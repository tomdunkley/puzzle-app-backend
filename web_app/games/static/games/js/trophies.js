(() => {
  async function init() {
    const loadingEl = document.getElementById('trophies-loading');
    const errorEl = document.getElementById('trophies-error');
    const gridEl = document.getElementById('trophies-grid');
    const authEl = document.getElementById('auth-notice');

    if (!API.isLoggedIn()) {
      loadingEl.style.display = 'none';
      authEl.style.display = '';
      return;
    }

    try {
      const trophies = await API.get('v1/trophies');
      loadingEl.style.display = 'none';

      if (!trophies || trophies.length === 0) {
        gridEl.style.display = '';
        gridEl.innerHTML = '<p style="color:var(--ink-mid); grid-column:1/-1">No trophies yet. Keep playing to earn some!</p>';
        return;
      }

      gridEl.style.display = '';
      gridEl.innerHTML = trophies.map(t => {
        const earned = !!t.earned_at;
        return `<div class="trophy-card${earned ? '' : ' trophy-locked'}">
          <div class="trophy-icon">${earned ? '🏆' : '🔒'}</div>
          <div class="trophy-name">${API.escHtml(t.name)}</div>
          <div class="trophy-desc">${API.escHtml(t.description)}</div>
          ${earned ? `<div class="trophy-date">${new Date(t.earned_at).toLocaleDateString()}</div>` : ''}
        </div>`;
      }).join('');
    } catch (e) {
      loadingEl.style.display = 'none';
      errorEl.style.display = '';
      errorEl.textContent = e.message || 'Failed to load trophies.';
    }
  }

  document.addEventListener('DOMContentLoaded', () => {
    API.ensureSession().then(init);
  });
})();
