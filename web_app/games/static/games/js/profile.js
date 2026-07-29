'use strict';

(() => {
  let myProfile = null;
  let searchDebounce = null;

  // ── Avatar / trophy helpers ────────────────────────────────────

  const AVATAR_EMOJI = {
    numbers: '🔢', words: '🔤', friend: '👥', flex: '💪', taunt: '😏',
    owl: '🦉', eight: '8️⃣', meta: '♾️', queen: '👑', santa: '🎅',
    sunglasses: '😎', bullseye: '🎯', fire: '🔥', bolt_icon: '⚡',
    star_icon: '⭐', shield: '🛡️', coffee: '☕', anchor: '⚓',
    heart: '❤️', music: '🎵', snowflake: '❄️', sun_icon: '☀️',
    lotus: '🌸', pizza: '🍕', cake: '🎂', egg: '🥚', raven: '🐦',
    route: '🛤️', map: '🗺️', compass: '🧭', trail: '🌿', globe: '🌐',
    mountain: '⛰️', wave: '🌊', mouse: '🐭', tree: '🌳', car: '🚗',
  };

  const COLOR_HEX = {
    gold: '#FFAA00', silver: '#C0C0C0', black: '#212121',
    purple: '#7B1FA2', teal: '#00695C', pink: '#E91E63', lime: '#558B2F',
    red: '#D32F2F', green: '#388E3C', blue: '#1565C0', orange: '#E65100',
  };

  function colorSwatch(colorId) {
    const hex = COLOR_HEX[colorId] || '#888';
    return `<span style="display:inline-block;width:1.3em;height:1.3em;background:${hex};border:1px solid rgba(0,0,0,0.15);border-radius:2px;vertical-align:middle"></span>`;
  }

  function trophyIcon(t) {
    if (!t.unlocked_at) return '🔒';
    if (t.unlocks_color_id) return colorSwatch(t.unlocks_color_id);
    if (t.unlocks_icon_color_id) return colorSwatch(t.unlocks_icon_color_id);
    if (t.unlocks_avatar_id) return AVATAR_EMOJI[t.unlocks_avatar_id] || '🏆';
    return '🏆';
  }

  function trophyGroup(t) {
    if (t.unlocked_at) return 0;
    if (!t.id.includes('streak')) return 1;
    if (t.id.startsWith('words_streak')) return 2;
    if (t.id.startsWith('numbers_streak')) return 3;
    if (t.id.startsWith('routes_streak')) return 4;
    return 5;
  }

  // ── Helpers ──────────────────────────────────────────────────────

  function show(elId) {
    document.getElementById('profile-loading').style.display = 'none';
    document.getElementById('profile-gate').style.display = 'none';
    document.getElementById('profile-content').style.display = 'none';
    document.getElementById(elId).style.display = '';
  }

  function avatarInitials(name) {
    return (name || '?').split(' ').map(w => w[0]).join('').slice(0, 2).toUpperCase();
  }

  function fmtTime(s) {
    if (s == null) return '?';
    const m = Math.floor(s / 60);
    return m > 0 ? `${m}m ${String(s % 60).padStart(2, '0')}s` : `${s}s`;
  }

  function fmtScore(game, today) {
    if (!today) return 'Not played today';
    if (game === 'numbers') {
      const d = today.distance ?? 1;
      if (d === 0) return `Exact! (${today.duration_seconds ?? 0}s)`;
      return `${today.result_value ?? '?'} (${d} away)`;
    }
    if (game === 'routes') return fmtTime(today.duration_seconds);
    return `${today.score ?? 0} pts (${today.word_count ?? 0} words)`;
  }

  function fmtBest(game, best) {
    if (!best) return '';
    if (game === 'numbers') {
      const d = best.distance ?? 1;
      if (d === 0) return 'Best: Exact!';
      return `Best: ${best.result_value} (${d} away)`;
    }
    if (game === 'routes') return `Best: ${fmtTime(best.duration_seconds)}`;
    return `Best: ${best.score} pts (${best.word_count ?? 0} words)`;
  }

  // ── Profile header ───────────────────────────────────────────────

  function renderHeader(profile) {
    const avatarEl = document.getElementById('profile-avatar');
    const emoji = profile.avatar_id && AVATAR_EMOJI[profile.avatar_id];
    const bg = profile.avatar_color_id && COLOR_HEX[profile.avatar_color_id];
    if (bg) { avatarEl.style.background = bg; avatarEl.style.color = '#fff'; }
    avatarEl.innerHTML = emoji
      ? `<span style="font-size:1.8rem;line-height:1">${emoji}</span>`
      : API.escHtml(avatarInitials(profile.display_name));
    document.getElementById('profile-display-name').textContent = profile.display_name;
    document.getElementById('settings-display-name').textContent = profile.display_name;
    document.getElementById('new-display-name').value = profile.display_name;

    const sub = [];
    if (profile.email) sub.push(profile.email);
    document.getElementById('profile-sub').textContent = sub.join(' · ');

    const vis = profile.visible_on_global_leaderboard !== false;
    document.getElementById('settings-visibility').textContent =
      vis ? 'Visible on global leaderboard' : 'Hidden from global leaderboard';

    if (profile.has_password) {
      document.getElementById('change-password-row').style.display = '';
    }
  }

  // ── Today's scores ───────────────────────────────────────────────

  async function loadTodayScores(userId) {
    try {
      const pub = await API.get(`v1/users/${userId}/profile`);
      document.getElementById('words-today-score').textContent = fmtScore('boggle', pub.today_boggle);
      document.getElementById('words-best-score').textContent = fmtBest('boggle', pub.boggle_daily_best);
      document.getElementById('numbers-today-score').textContent = fmtScore('numbers', pub.today_numbers);
      document.getElementById('numbers-best-score').textContent = fmtBest('numbers', pub.numbers_daily_best);
      document.getElementById('routes-today-score').textContent = fmtScore('routes', pub.today_routes);
      document.getElementById('routes-best-score').textContent = fmtBest('routes', pub.routes_daily_best);
    } catch (_) { /* ignore */ }
  }

  // ── Trophies ─────────────────────────────────────────────────────

  async function loadTrophies() {
    const gridEl = document.getElementById('trophies-grid');
    const emptyEl = document.getElementById('trophies-empty');
    const badgeEl = document.getElementById('trophy-count-badge');
    try {
      const resp = await API.get('v1/users/me/achievements');
      const trophies = resp.achievements || [];
      const earned = trophies.filter(t => t.unlocked_at);
      badgeEl.textContent = `${earned.length} / ${trophies.length}`;
      if (trophies.length === 0) { emptyEl.style.display = ''; return; }

      // Sort: unlocked newest first → non-streak locked → words-streak locked → numbers-streak locked
      const sorted = [...trophies].sort((a, b) => {
        const ga = trophyGroup(a), gb = trophyGroup(b);
        if (ga !== gb) return ga - gb;
        if (ga === 0) return new Date(b.unlocked_at) - new Date(a.unlocked_at);
        return 0;
      });

      gridEl.innerHTML = sorted.map(t => {
        const isEarned = !!t.unlocked_at;
        const icon = trophyIcon(t);
        const desc = isEarned ? API.escHtml(t.description) : '?????';
        return `<div class="trophy-card${isEarned ? '' : ' trophy-locked'}">
          <div class="trophy-icon">${icon}</div>
          <div class="trophy-name">${API.escHtml(t.title)}</div>
          <div class="trophy-desc">${desc}</div>
          ${isEarned ? `<div class="trophy-date">${new Date(t.unlocked_at).toLocaleDateString()}</div>` : ''}
        </div>`;
      }).join('');
    } catch (_) { emptyEl.style.display = ''; }
  }

  // ── Friends ──────────────────────────────────────────────────────

  function friendActionHtml(user) {
    const uid = API.escHtml(user.user_id);
    switch (user.friendship_status) {
      case 'friends':
        return `<button class="btn btn-ghost btn-sm" onclick="ProfFriends.unfriend('${uid}',this)">Remove</button>`;
      case 'request_sent':
        return `<span class="badge">Sent</span>`;
      case 'request_received':
        return `<button class="btn btn-primary btn-sm" onclick="ProfFriends.accept('${uid}',this)">Accept</button>
                <button class="btn btn-ghost btn-sm" onclick="ProfFriends.decline('${uid}',this)">Decline</button>`;
      default:
        return `<button class="btn btn-secondary btn-sm" onclick="ProfFriends.sendRequest('${uid}',this)">Add</button>`;
    }
  }

  function renderUserRow(user, actionHtml) {
    const slug = (user.display_name || '').toLowerCase().replace(/\s+/g, '_');
    const profileUrl = `/users/${API.escHtml(slug)}/`;
    return `<div class="friend-row">
      <a href="${profileUrl}" class="friend-name" style="text-decoration:none;color:inherit">${API.escHtml(user.display_name)}</a>
      <span class="friend-actions">${actionHtml}</span>
    </div>`;
  }

  async function loadFriends() {
    const listEl = document.getElementById('friends-list');
    try {
      const friends = await API.get('v1/friends');
      if (!friends || friends.length === 0) {
        listEl.innerHTML = '<p style="color:var(--ink-mid); font-size:0.88rem; padding:8px 0">No friends yet. Search above to find people.</p>';
        return;
      }
      listEl.innerHTML = friends.map(f =>
        renderUserRow({ display_name: f.display_name, user_id: f.user_id }, `<button class="btn btn-ghost btn-sm" onclick="ProfFriends.unfriend('${API.escHtml(f.user_id)}',this)">Remove</button>`)
      ).join('');
    } catch (_) { listEl.innerHTML = ''; }
  }

  async function loadRequests() {
    try {
      const incoming = await API.get('v1/friends/requests/incoming');
      const section = document.getElementById('friend-requests-section');
      const listEl = document.getElementById('friend-requests-list');
      if (!incoming || incoming.length === 0) { section.style.display = 'none'; return; }
      section.style.display = '';
      listEl.innerHTML = incoming.map(r =>
        renderUserRow(r, `<button class="btn btn-primary btn-sm" onclick="ProfFriends.accept('${API.escHtml(r.user_id)}',this)">Accept</button>
                          <button class="btn btn-ghost btn-sm" onclick="ProfFriends.decline('${API.escHtml(r.user_id)}',this)">Decline</button>`)
      ).join('');
    } catch (_) { /* ignore */ }
  }

  async function searchFriends(q) {
    const resultsEl = document.getElementById('search-results');
    if (!q || q.length < 2) { resultsEl.innerHTML = ''; return; }
    resultsEl.innerHTML = '<p style="padding:8px 0; color:var(--ink-mid); font-size:0.88rem">Searching…</p>';
    try {
      const res = await API.get(`v1/users/search?q=${encodeURIComponent(q)}`);
      if (!res || res.length === 0) {
        resultsEl.innerHTML = '<p style="padding:8px 0; color:var(--ink-mid); font-size:0.88rem">No users found.</p>';
        return;
      }
      resultsEl.innerHTML = res.map(u => renderUserRow(u, friendActionHtml(u))).join('');
    } catch (e) {
      resultsEl.innerHTML = `<p class="alert alert-error">${API.escHtml(e.message)}</p>`;
    }
  }

  window.ProfFriends = {
    async sendRequest(userId, btn) {
      btn.disabled = true;
      try {
        await API.post('v1/friends/requests', { to_user_id: userId });
        btn.closest('.friend-actions').innerHTML = '<span class="badge">Sent</span>';
        loadFriends();
      } catch (e) { btn.disabled = false; alert(e.message); }
    },
    async accept(userId, btn) {
      btn.disabled = true;
      try {
        await API.post(`v1/friends/requests/${userId}/accept`);
        btn.closest('.friend-row').remove();
        await Promise.all([loadFriends(), loadRequests()]);
      } catch (e) { btn.disabled = false; alert(e.message); }
    },
    async decline(userId, btn) {
      btn.disabled = true;
      try {
        await API.post(`v1/friends/requests/${userId}/decline`);
        btn.closest('.friend-row').remove();
        loadRequests();
      } catch (e) { btn.disabled = false; alert(e.message); }
    },
    async unfriend(userId, btn) {
      if (!confirm('Remove this friend?')) return;
      btn.disabled = true;
      try {
        await API.del(`v1/friends/${userId}`);
        btn.closest('.friend-row').remove();
      } catch (e) { btn.disabled = false; alert(e.message); }
    },
  };

  // ── Account settings ─────────────────────────────────────────────

  function setupSettings(profile) {
    const editNameBtn = document.getElementById('edit-name-btn');
    const editNameForm = document.getElementById('edit-name-form');
    const saveNameBtn = document.getElementById('save-name-btn');
    const cancelNameBtn = document.getElementById('cancel-name-btn');
    const nameInput = document.getElementById('new-display-name');
    const nameError = document.getElementById('edit-name-error');

    editNameBtn.addEventListener('click', () => {
      editNameForm.style.display = '';
      editNameBtn.style.display = 'none';
    });
    cancelNameBtn.addEventListener('click', () => {
      editNameForm.style.display = 'none';
      editNameBtn.style.display = '';
      nameError.style.display = 'none';
    });
    saveNameBtn.addEventListener('click', async () => {
      const name = nameInput.value.trim();
      if (!name) return;
      saveNameBtn.disabled = true;
      nameError.style.display = 'none';
      try {
        const updated = await API.patch('v1/users/me', { display_name: name });
        localStorage.setItem('td_display_name', updated.display_name);
        document.getElementById('profile-display-name').textContent = updated.display_name;
        document.getElementById('settings-display-name').textContent = updated.display_name;
        editNameForm.style.display = 'none';
        editNameBtn.style.display = '';
        Auth.updateNav();
      } catch (e) {
        nameError.textContent = e.message;
        nameError.style.display = '';
      } finally { saveNameBtn.disabled = false; }
    });

    const toggleVisBtn = document.getElementById('toggle-visibility-btn');
    toggleVisBtn.addEventListener('click', async () => {
      const current = myProfile.visible_on_global_leaderboard !== false;
      try {
        const updated = await API.patch('v1/users/me', { visible_on_global_leaderboard: !current });
        myProfile = updated;
        document.getElementById('settings-visibility').textContent =
          updated.visible_on_global_leaderboard ? 'Visible on global leaderboard' : 'Hidden from global leaderboard';
      } catch (e) { alert(e.message); }
    });

    document.getElementById('logout-btn').addEventListener('click', () => Auth.logout());

    const deleteBtn = document.getElementById('delete-account-btn');
    const deleteConfirm = document.getElementById('delete-confirm');
    const deleteCancelBtn = document.getElementById('delete-cancel-btn');
    const deleteConfirmBtn = document.getElementById('delete-confirm-btn');

    deleteBtn.addEventListener('click', () => { deleteConfirm.style.display = ''; });
    deleteCancelBtn.addEventListener('click', () => { deleteConfirm.style.display = 'none'; });
    deleteConfirmBtn.addEventListener('click', async () => {
      deleteConfirmBtn.disabled = true;
      try {
        await API.del('v1/users/me');
        localStorage.clear();
        window.location.href = '/';
      } catch (e) {
        alert(e.message);
        deleteConfirmBtn.disabled = false;
      }
    });
  }

  // ── Search input wiring ──────────────────────────────────────────

  function setupSearch() {
    document.getElementById('friend-search').addEventListener('input', e => {
      clearTimeout(searchDebounce);
      searchDebounce = setTimeout(() => searchFriends(e.target.value.trim()), 300);
    });
    document.getElementById('friend-search-btn').addEventListener('click', () => {
      searchFriends(document.getElementById('friend-search').value.trim());
    });
  }

  // ── Init ─────────────────────────────────────────────────────────

  async function init() {
    if (!API.isLoggedIn()) { show('profile-gate'); return; }

    try {
      myProfile = await API.get('v1/users/me');
      show('profile-content');
      renderHeader(myProfile);
      setupSettings(myProfile);
      setupSearch();
      await Promise.all([
        loadTodayScores(myProfile.user_id),
        loadTrophies(),
        loadFriends(),
        loadRequests(),
      ]);
    } catch (e) {
      show('profile-gate');
    }
  }

  document.addEventListener('DOMContentLoaded', init);
})();
