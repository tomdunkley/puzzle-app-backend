'use strict';

// Shared leaderboard rendering helper used by boggle.js and numbers.js.
const Leaderboard = (() => {

    // Render friends + global leaderboard tabs into `containerEl` for the given puzzleId.
    // `formatScore` is a function(entry) -> string for the score column.
    // `myUserId` is the logged-in user's ID (or null).
    async function render(containerEl, puzzleId, formatScore, myUserId) {
        if (!API.isLoggedIn()) {
            containerEl.innerHTML = `
                <div class="lb-auth-gate">
                    <a href="/login/">Sign in</a> to see how you rank against friends.
                </div>`;
            return;
        }

        containerEl.innerHTML = `
            <div class="lb-tabs">
                <button class="lb-tab active" data-tab="friends">Friends</button>
                <button class="lb-tab" data-tab="global">Global</button>
            </div>
            <div id="lb-panel-friends"></div>
            <div id="lb-panel-global" style="display:none"></div>`;

        const friendsPanel = containerEl.querySelector('#lb-panel-friends');
        const globalPanel  = containerEl.querySelector('#lb-panel-global');

        containerEl.querySelectorAll('.lb-tab').forEach(tab => {
            tab.addEventListener('click', () => {
                containerEl.querySelectorAll('.lb-tab').forEach(t => t.classList.remove('active'));
                tab.classList.add('active');
                friendsPanel.style.display = tab.dataset.tab === 'friends' ? '' : 'none';
                globalPanel.style.display  = tab.dataset.tab === 'global'  ? '' : 'none';
            });
        });

        // Load both in parallel
        const [friendsData, globalData] = await Promise.allSettled([
            API.get(`v1/leaderboards/${puzzleId}`),
            API.get(`v1/leaderboards/${puzzleId}/global`),
        ]);

        renderPanel(friendsPanel, friendsData.status === 'fulfilled' ? friendsData.value : [], myUserId, formatScore, 'friends');
        renderPanel(globalPanel,  globalData.status  === 'fulfilled' ? globalData.value  : [], myUserId, formatScore, 'global');
    }

    function renderPanel(panel, entries, myUserId, formatScore, scope) {
        if (!entries || !entries.entries || entries.entries.length === 0) {
            panel.innerHTML = `<div class="empty-state" style="padding:20px 0">
                <p>${scope === 'friends' ? 'Add friends to see them here.' : 'No scores yet.'}</p>
            </div>`;
            return;
        }
        const rows = entries.entries.map((e, i) => {
            const isSelf = e.user_id === myUserId;
            const name = API.escHtml(e.display_name || 'Unknown');
            const youBadge = isSelf ? '<span class="you-badge">you</span>' : '';
            const profileUrl = `/users/${API.escHtml(e.user_id)}/`;
            return `<tr class="${isSelf ? 'self-row' : ''}">
                <td class="rank-col">${i + 1}</td>
                <td><a href="${profileUrl}" style="text-decoration:none;color:inherit">${name}</a>${youBadge}</td>
                <td class="score-col">${API.escHtml(String(formatScore(e)))}</td>
            </tr>`;
        }).join('');
        panel.innerHTML = `
            <table class="lb-table">
                <thead><tr>
                    <th class="rank-col">#</th>
                    <th>Player</th>
                    <th class="score-col">Score</th>
                </tr></thead>
                <tbody>${rows}</tbody>
            </table>`;
    }

    return { render };
})();
