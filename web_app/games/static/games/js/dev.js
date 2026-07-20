'use strict';

(() => {
  let pendingDeleteId = null;

  function yn(val) {
    return val ? '<span class="badge-yes">Yes</span>' : '<span class="badge-no">No</span>';
  }

  function fmtDate(iso) {
    if (!iso) return '—';
    try {
      const d = new Date(iso);
      return d.toLocaleDateString() + ' ' + d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    } catch { return iso; }
  }

  function renderRow(u) {
    const uid = API.escHtml(u.user_id || '');
    const slug = API.escHtml((u.display_name || '').toLowerCase().replace(/\s+/g, '_'));
    return `<tr>
      <td><a href="/users/${slug}/" style="color:inherit;text-decoration:none">${API.escHtml(u.display_name || '—')}</a></td>
      <td style="font-size:0.72rem;color:var(--ink-mid)">${uid}</td>
      <td>${API.escHtml(u.email || '—')}</td>
      <td>${yn(u.email_verified)}</td>
      <td>${yn(u.is_developer)}</td>
      <td>${yn(u.visible_on_global_leaderboard !== false)}</td>
      <td>${yn(u.is_guest)}</td>
      <td>${fmtDate(u.created_at)}</td>
      <td class="actions-col">
        <button class="btn btn-secondary btn-sm" style="margin-right:4px" onclick="DevAdmin.toggle('${uid}','email_verified',${!u.email_verified},this)">
          ${u.email_verified ? 'Unverify' : 'Verify'}
        </button>
        <button class="btn btn-secondary btn-sm" style="margin-right:4px" onclick="DevAdmin.toggle('${uid}','is_developer',${!u.is_developer},this)">
          ${u.is_developer ? 'Revoke dev' : 'Make dev'}
        </button>
        <button class="btn btn-danger btn-sm" onclick="DevAdmin.confirmDelete('${uid}','${API.escHtml(u.display_name || uid)}')">
          Delete
        </button>
      </td>
    </tr>`;
  }

  async function loadUsers() {
    const tbody = document.getElementById('dev-users-tbody');
    const errEl = document.getElementById('dev-error');
    const countEl = document.getElementById('dev-user-count');
    errEl.style.display = 'none';
    tbody.innerHTML = '<tr><td colspan="9" style="color:var(--ink-mid);padding:16px 8px">Loading…</td></tr>';
    try {
      const users = await API.get('v1/dev/users');
      countEl.textContent = `${users.length} users`;
      if (users.length === 0) {
        tbody.innerHTML = '<tr><td colspan="9" style="color:var(--ink-mid);padding:16px 8px">No users found.</td></tr>';
        return;
      }
      tbody.innerHTML = users.map(renderRow).join('');
    } catch (e) {
      tbody.innerHTML = '';
      errEl.style.display = '';
      document.getElementById('dev-error-msg').textContent = e.message || 'Failed to load users.';
    }
  }

  window.DevAdmin = {
    async toggle(userId, field, newVal, btn) {
      btn.disabled = true;
      try {
        await API.patch(`v1/dev/users/${userId}`, { [field]: newVal });
        await loadUsers();
      } catch (e) {
        btn.disabled = false;
        alert(e.message);
      }
    },
    confirmDelete(userId, displayName) {
      pendingDeleteId = userId;
      document.getElementById('dev-confirm-msg').textContent =
        `Delete "${displayName}"? This is permanent and cannot be undone.`;
      const modal = document.getElementById('dev-confirm-modal');
      modal.style.display = 'flex';
    },
  };

  document.getElementById('dev-confirm-yes').addEventListener('click', async () => {
    if (!pendingDeleteId) return;
    const btn = document.getElementById('dev-confirm-yes');
    btn.disabled = true;
    try {
      await API.del(`v1/dev/users/${pendingDeleteId}`);
      document.getElementById('dev-confirm-modal').style.display = 'none';
      pendingDeleteId = null;
      await loadUsers();
    } catch (e) {
      alert(e.message);
    } finally { btn.disabled = false; }
  });

  document.getElementById('dev-confirm-no').addEventListener('click', () => {
    document.getElementById('dev-confirm-modal').style.display = 'none';
    pendingDeleteId = null;
  });

  document.getElementById('dev-refresh-btn').addEventListener('click', loadUsers);

  async function init() {
    const loadingEl = document.getElementById('dev-loading');
    const gateEl = document.getElementById('dev-gate');
    const contentEl = document.getElementById('dev-content');

    if (!API.isLoggedIn()) {
      loadingEl.style.display = 'none';
      gateEl.style.display = '';
      return;
    }

    try {
      const me = await API.get('v1/users/me');
      loadingEl.style.display = 'none';
      if (!me.is_developer) {
        gateEl.style.display = '';
        return;
      }
      contentEl.style.display = '';
      await loadUsers();
    } catch (_) {
      loadingEl.style.display = 'none';
      gateEl.style.display = '';
    }
  }

  document.addEventListener('DOMContentLoaded', init);
})();
