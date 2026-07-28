'use strict';

(() => {
  // Extract name slug from URL path, e.g. /users/tomdunkley/ → "tomdunkley"
  const nameSlug = (window.location.pathname.match(/\/users\/([^/]+)\//) || [])[1];

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

  function avatarInitials(name) {
    return (name || '?').split(' ').map(w => w[0]).join('').slice(0, 2).toUpperCase();
  }

  function renderFriendAction(profile) {
    const el = document.getElementById('up-friend-action');
    if (!API.isLoggedIn()) { el.innerHTML = ''; return; }
    const uid = API.escHtml(profile.user_id);
    switch (profile.friendship_status) {
      case 'self':
        el.innerHTML = `<a href="/profile/" class="btn btn-secondary btn-sm">Edit profile</a>`;
        break;
      case 'friends':
        el.innerHTML = `<button class="btn btn-ghost btn-sm" onclick="UPActions.unfriend('${uid}',this)">Remove friend</button>`;
        break;
      case 'request_sent':
        el.innerHTML = `<span class="badge" style="padding:8px 12px">Friend request sent</span>`;
        break;
      case 'request_received':
        el.innerHTML = `<button class="btn btn-primary btn-sm" onclick="UPActions.accept('${uid}',this)">Accept request</button>`;
        break;
      default:
        el.innerHTML = `<button class="btn btn-secondary btn-sm" onclick="UPActions.addFriend('${uid}',this)">Add friend</button>`;
    }
  }

  window.UPActions = {
    async addFriend(uid, btn) {
      btn.disabled = true;
      try {
        await API.post('v1/friends/requests', { to_user_id: uid });
        document.getElementById('up-friend-action').innerHTML =
          '<span class="badge" style="padding:8px 12px">Friend request sent</span>';
      } catch (e) { btn.disabled = false; alert(e.message); }
    },
    async accept(uid, btn) {
      btn.disabled = true;
      try {
        await API.post(`v1/friends/requests/${uid}/accept`);
        document.getElementById('up-friend-action').innerHTML =
          '<button class="btn btn-ghost btn-sm" onclick="UPActions.unfriend(\'' + uid + '\',this)">Remove friend</button>';
      } catch (e) { btn.disabled = false; alert(e.message); }
    },
    async unfriend(uid, btn) {
      if (!confirm('Remove this friend?')) return;
      btn.disabled = true;
      try {
        await API.del(`v1/friends/${uid}`);
        document.getElementById('up-friend-action').innerHTML =
          '<button class="btn btn-secondary btn-sm" onclick="UPActions.addFriend(\'' + uid + '\',this)">Add friend</button>';
      } catch (e) { btn.disabled = false; alert(e.message); }
    },
  };

  async function init() {
    const loadingEl = document.getElementById('up-loading');
    const errorEl = document.getElementById('up-error');
    const contentEl = document.getElementById('up-content');

    try {
      // Try by display name first; fall back to user ID for any old links
      let profile;
      try {
        profile = await API.get(`v1/users/by-name/${encodeURIComponent(nameSlug)}`);
      } catch (nameErr) {
        if (nameErr.status === 404) {
          profile = await API.get(`v1/users/${nameSlug}/profile`);
        } else {
          throw nameErr;
        }
      }

      loadingEl.style.display = 'none';
      contentEl.style.display = '';

      document.getElementById('up-avatar').textContent = avatarInitials(profile.display_name);
      document.getElementById('up-display-name').textContent = profile.display_name;

      // Trophy count sub-line
      document.getElementById('up-sub').textContent = `${profile.trophy_count} / ${profile.total_trophies} trophies`;

      renderFriendAction(profile);

      // Today's scores
      document.getElementById('up-words-today').textContent = fmtScore('boggle', profile.today_boggle);
      document.getElementById('up-words-best').textContent = fmtBest('boggle', profile.boggle_daily_best);
      document.getElementById('up-numbers-today').textContent = fmtScore('numbers', profile.today_numbers);
      document.getElementById('up-numbers-best').textContent = fmtBest('numbers', profile.numbers_daily_best);
      document.getElementById('up-routes-today').textContent = fmtScore('routes', profile.today_routes);
      document.getElementById('up-routes-best').textContent = fmtBest('routes', profile.routes_daily_best);

      // Trophies — load full list
      const trophyBadge = document.getElementById('up-trophy-badge');
      trophyBadge.textContent = `${profile.trophy_count} / ${profile.total_trophies}`;

      // We can only show trophy details for own profile or if we have access;
      // the public profile just shows count. Show a simple count message.
      const trophyGrid = document.getElementById('up-trophy-grid');
      const trophyEmpty = document.getElementById('up-trophy-empty');
      if (profile.trophy_count === 0) {
        trophyEmpty.style.display = '';
      } else {
        trophyGrid.innerHTML = `<p style="color:var(--ink-mid); font-size:0.88rem">${profile.trophy_count} trophy${profile.trophy_count !== 1 ? 'ies' : 'y'} unlocked.</p>`;
      }

    } catch (e) {
      loadingEl.style.display = 'none';
      if (e.status === 401) {
        errorEl.style.display = '';
        document.getElementById('up-error-msg').innerHTML =
          '<a href="/login/">Sign in</a> to view player profiles.';
      } else {
        errorEl.style.display = '';
        document.getElementById('up-error-msg').textContent = e.message || 'Profile not found.';
      }
    }
  }

  document.addEventListener('DOMContentLoaded', init);
})();
