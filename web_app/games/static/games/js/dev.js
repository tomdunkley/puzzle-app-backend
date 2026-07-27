'use strict';

(() => {
  const PAGE_SIZE = 20;
  let allUsers = [];
  let filteredUsers = [];
  let currentPage = 0;
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
    const platform = u.last_login_platform ? `<span style="font-size:0.75rem;color:var(--ink-mid)">(${API.escHtml(u.last_login_platform)})</span>` : '';
    return `<tr>
      <td><a href="/users/${slug}/" style="color:inherit;text-decoration:none">${API.escHtml(u.display_name || '—')}</a></td>
      <td style="font-size:0.72rem;color:var(--ink-mid)">${uid}</td>
      <td>${API.escHtml(u.email || '—')}</td>
      <td>${yn(u.email_verified)}</td>
      <td>${yn(u.is_developer)}</td>
      <td>${yn(u.visible_on_global_leaderboard !== false)}</td>
      <td>${yn(u.is_guest)}</td>
      <td>${fmtDate(u.created_at)}</td>
      <td>${fmtDate(u.last_login_at)} ${platform}</td>
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

  function applyFilter() {
    const search = (document.getElementById('dev-search').value || '').toLowerCase();
    const type = document.getElementById('dev-type-filter').value;
    filteredUsers = allUsers.filter(u => {
      if (search) {
        const name = (u.display_name || '').toLowerCase();
        const email = (u.email || '').toLowerCase();
        if (!name.includes(search) && !email.includes(search)) return false;
      }
      if (type === 'real' && u.is_guest) return false;
      if (type === 'guest' && !u.is_guest) return false;
      if (type === 'dev' && !u.is_developer) return false;
      return true;
    });
    currentPage = 0;
    renderPage();
  }

  function renderPage() {
    const tbody = document.getElementById('dev-users-tbody');
    const countEl = document.getElementById('dev-user-count');
    const pageInfo = document.getElementById('dev-page-info');
    const prevBtn = document.getElementById('dev-prev-btn');
    const nextBtn = document.getElementById('dev-next-btn');
    const totalPages = Math.max(1, Math.ceil(filteredUsers.length / PAGE_SIZE));
    const start = currentPage * PAGE_SIZE;
    const page = filteredUsers.slice(start, start + PAGE_SIZE);
    const colCount = 10;

    countEl.textContent = `${filteredUsers.length} / ${allUsers.length} users`;
    pageInfo.textContent = `Page ${currentPage + 1} of ${totalPages}`;
    prevBtn.disabled = currentPage === 0;
    nextBtn.disabled = currentPage >= totalPages - 1;

    if (filteredUsers.length === 0) {
      tbody.innerHTML = `<tr><td colspan="${colCount}" style="color:var(--ink-mid);padding:16px 8px">No users match the filter.</td></tr>`;
    } else {
      tbody.innerHTML = page.map(renderRow).join('');
    }
  }

  async function loadUsers() {
    const tbody = document.getElementById('dev-users-tbody');
    const errEl = document.getElementById('dev-error');
    errEl.style.display = 'none';
    tbody.innerHTML = '<tr><td colspan="10" style="color:var(--ink-mid);padding:16px 8px">Loading…</td></tr>';
    try {
      allUsers = await API.get('v1/dev/users');
      applyFilter();
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
  document.getElementById('dev-search').addEventListener('input', applyFilter);
  document.getElementById('dev-type-filter').addEventListener('change', applyFilter);
  document.getElementById('dev-prev-btn').addEventListener('click', () => {
    if (currentPage > 0) { currentPage--; renderPage(); }
  });
  document.getElementById('dev-next-btn').addEventListener('click', () => {
    const totalPages = Math.ceil(filteredUsers.length / PAGE_SIZE);
    if (currentPage < totalPages - 1) { currentPage++; renderPage(); }
  });

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
