(() => {
  let searchDebounce = null;

  function renderUserRow(user, actionHtml) {
    return `<div class="friend-row">
      <span class="friend-name">${API.escHtml(user.display_name)}</span>
      <span class="friend-actions">${actionHtml}</span>
    </div>`;
  }

  function actionForStatus(user) {
    switch (user.friendship_status) {
      case 'friends':
        return `<button class="btn btn-ghost btn-sm" onclick="Frnds.unfriend('${user.user_id}', this)">Remove</button>`;
      case 'request_sent':
        return `<span class="badge">Request sent</span>`;
      case 'request_received':
        return `<button class="btn btn-primary btn-sm" onclick="Frnds.accept('${user.user_id}', this)">Accept</button>`;
      default:
        return `<button class="btn btn-secondary btn-sm" onclick="Frnds.sendRequest('${user.user_id}', this)">Add</button>`;
    }
  }

  async function search(q) {
    const resultsEl = document.getElementById('search-results');
    if (!q || q.length < 2) { resultsEl.innerHTML = ''; return; }
    resultsEl.innerHTML = '<p style="padding:8px; color:var(--ink-mid)">Searching…</p>';
    try {
      const res = await API.get(`v1/users/search?q=${encodeURIComponent(q)}`);
      if (res.length === 0) {
        resultsEl.innerHTML = '<p style="padding:8px; color:var(--ink-mid)">No users found.</p>';
        return;
      }
      resultsEl.innerHTML = res.map(u => renderUserRow(u, actionForStatus(u))).join('');
    } catch (e) {
      resultsEl.innerHTML = `<p class="alert alert-error">${API.escHtml(e.message)}</p>`;
    }
  }

  async function loadFriends() {
    const listEl = document.getElementById('friends-list');
    try {
      const friends = await API.get('v1/friends');
      if (friends.length === 0) {
        listEl.innerHTML = '<p style="color:var(--ink-mid)">No friends yet. Use the search above to find people!</p>';
        return;
      }
      listEl.innerHTML = friends.map(f => renderUserRow(
        { display_name: f.display_name, user_id: f.user_id },
        `<button class="btn btn-ghost btn-sm" onclick="Frnds.unfriend('${f.user_id}', this)">Remove</button>`
      )).join('');
    } catch (e) {
      listEl.innerHTML = `<p class="alert alert-error">${API.escHtml(e.message)}</p>`;
    }
  }

  async function loadRequests() {
    try {
      const incoming = await API.get('v1/friends/requests/incoming');
      const section = document.getElementById('requests-section');
      const listEl = document.getElementById('requests-list');
      if (incoming.length === 0) { section.style.display = 'none'; return; }
      section.style.display = '';
      listEl.innerHTML = incoming.map(r => renderUserRow(
        { display_name: r.display_name, user_id: r.user_id },
        `<button class="btn btn-primary btn-sm" onclick="Frnds.accept('${r.user_id}', this)">Accept</button>
         <button class="btn btn-ghost btn-sm" onclick="Frnds.decline('${r.user_id}', this)">Decline</button>`
      )).join('');
    } catch { /* ignore */ }
  }

  // Public action handlers (called from inline onclick — must be on window)
  window.Frnds = {
    async sendRequest(userId, btn) {
      btn.disabled = true;
      try {
        await API.post('v1/friends/requests', { to_user_id: userId });
        btn.closest('.friend-actions').innerHTML = '<span class="badge">Request sent</span>';
        loadFriends();
      } catch (e) {
        btn.disabled = false;
        alert(e.message);
      }
    },
    async accept(userId, btn) {
      btn.disabled = true;
      try {
        await API.post(`v1/friends/requests/${userId}/accept`);
        btn.closest('.friend-row').remove();
        loadFriends();
        loadRequests();
      } catch (e) {
        btn.disabled = false;
        alert(e.message);
      }
    },
    async decline(userId, btn) {
      btn.disabled = true;
      try {
        await API.post(`v1/friends/requests/${userId}/decline`);
        btn.closest('.friend-row').remove();
        loadRequests();
      } catch (e) {
        btn.disabled = false;
        alert(e.message);
      }
    },
    async unfriend(userId, btn) {
      if (!confirm('Remove this friend?')) return;
      btn.disabled = true;
      try {
        await API.del(`v1/friends/${userId}`);
        btn.closest('.friend-row').remove();
      } catch (e) {
        btn.disabled = false;
        alert(e.message);
      }
    },
  };

  async function init() {
    if (!API.isLoggedIn()) {
      document.getElementById('auth-notice').style.display = '';
      return;
    }
    document.getElementById('friends-content').style.display = '';
    await Promise.all([loadFriends(), loadRequests()]);
  }

  document.addEventListener('DOMContentLoaded', () => {
    document.getElementById('search-input').addEventListener('input', e => {
      clearTimeout(searchDebounce);
      searchDebounce = setTimeout(() => search(e.target.value.trim()), 300);
    });
    API.ensureSession().then(init);
  });
})();
