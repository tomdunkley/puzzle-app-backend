(() => {
  let activeTab = 'boggle';

  function show(tabId) {
    document.querySelectorAll('.tab').forEach(t => t.classList.toggle('active', t.dataset.tab === tabId));
    document.getElementById('tab-boggle').style.display = tabId === 'boggle' ? '' : 'none';
    document.getElementById('tab-numbers').style.display = tabId === 'numbers' ? '' : 'none';
    activeTab = tabId;
  }

  document.querySelectorAll('.tab').forEach(t => {
    t.addEventListener('click', () => show(t.dataset.tab));
  });

  function renderBoggleRow(entry, rank, selfId) {
    const isSelf = entry.user_id === selfId;
    return `<tr class="${isSelf ? 'self-row' : ''}">
      <td>${rank}</td>
      <td>${API.escHtml(entry.display_name)}${isSelf ? ' <span class="you-badge">you</span>' : ''}</td>
      <td>${entry.score}</td>
      <td>${entry.word_count ?? '—'}</td>
    </tr>`;
  }

  function renderNumbersRow(entry, rank, selfId) {
    const isSelf = entry.user_id === selfId;
    const closest = entry.closest_value;
    const tgt = entry.target;
    const result = closest === tgt ? `${closest} ✓` : `${closest} (${Math.abs(closest - tgt)} away)`;
    return `<tr class="${isSelf ? 'self-row' : ''}">
      <td>${rank}</td>
      <td>${API.escHtml(entry.display_name)}${isSelf ? ' <span class="you-badge">you</span>' : ''}</td>
      <td>${result}</td>
      <td>${entry.step_count ?? '—'}</td>
    </tr>`;
  }

  async function loadLeaderboard(game) {
    const loadingEl = document.getElementById(`${game}-loading`);
    const errorEl = document.getElementById(`${game}-error`);
    const tableEl = document.getElementById(`${game}-table`);
    const tbodyEl = document.getElementById(`${game}-tbody`);
    const emptyEl = document.getElementById(`${game}-empty`);

    loadingEl.style.display = '';
    errorEl.style.display = 'none';
    tableEl.style.display = 'none';
    emptyEl.style.display = 'none';

    try {
      const puzzleData = await API.get(`v1/puzzles/today?game=${game}`);
      const puzzleId = puzzleData.puzzle_id;

      const lb = await API.get(`v1/leaderboards/${puzzleId}`);
      loadingEl.style.display = 'none';

      const selfId = lb.user_id;
      const entries = lb.entries || [];

      if (entries.length === 0) {
        emptyEl.style.display = '';
        return;
      }

      tableEl.style.display = '';
      if (game === 'boggle') {
        tbodyEl.innerHTML = entries.map((e, i) => renderBoggleRow(e, i + 1, selfId)).join('');
      } else {
        tbodyEl.innerHTML = entries.map((e, i) => renderNumbersRow(e, i + 1, selfId)).join('');
      }
    } catch (e) {
      loadingEl.style.display = 'none';
      errorEl.style.display = '';
      errorEl.textContent = e.message || 'Failed to load leaderboard.';
    }
  }

  async function init() {
    if (!API.isLoggedIn()) {
      document.getElementById('auth-notice').style.display = '';
      document.getElementById('tab-boggle').style.display = 'none';
      document.getElementById('tab-numbers').style.display = 'none';
      document.querySelector('.tab-bar').style.display = 'none';
      return;
    }
    await Promise.all([loadLeaderboard('boggle'), loadLeaderboard('numbers')]);
    show('boggle');
  }

  document.addEventListener('DOMContentLoaded', () => {
    API.ensureSession().then(init);
  });
})();
