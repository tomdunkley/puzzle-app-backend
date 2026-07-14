'use strict';

// Central API client. TD_API_BASE is injected by base.html.
const API = (() => {
    const base = () => window.TD_API_BASE.replace(/\/$/, '');

    function escHtml(str) {
        const d = document.createElement('div');
        d.appendChild(document.createTextNode(String(str)));
        return d.innerHTML;
    }

    async function rawFetch(path, opts) {
        return fetch(base() + '/' + path, opts);
    }

    async function tryRefresh() {
        const rt = localStorage.getItem('td_refresh_token');
        if (!rt) return false;
        try {
            const res = await rawFetch('v1/auth/refresh', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ refresh_token: rt }),
            });
            if (!res.ok) throw new Error('expired');
            const { access_token, refresh_token } = await res.json();
            localStorage.setItem('td_access_token', access_token);
            localStorage.setItem('td_refresh_token', refresh_token);
            return true;
        } catch {
            localStorage.removeItem('td_access_token');
            localStorage.removeItem('td_refresh_token');
            localStorage.removeItem('td_is_guest');
            localStorage.removeItem('td_display_name');
            return false;
        }
    }

    async function request(method, path, body) {
        const makeOpts = () => {
            const token = localStorage.getItem('td_access_token');
            const headers = { 'Content-Type': 'application/json' };
            if (token) headers['Authorization'] = 'Bearer ' + token;
            return {
                method,
                headers,
                body: body !== undefined ? JSON.stringify(body) : undefined,
            };
        };

        let res = await rawFetch(path, makeOpts());

        if (res.status === 401) {
            const refreshed = await tryRefresh();
            if (refreshed) res = await rawFetch(path, makeOpts());
        }

        if (!res.ok) {
            let detail = `HTTP ${res.status}`;
            try { detail = (await res.clone().json()).detail || detail; } catch {}
            const err = new Error(detail);
            err.status = res.status;
            throw err;
        }

        const text = await res.text();
        return text ? JSON.parse(text) : null;
    }

    // Silently create a guest session if there are no credentials at all.
    async function ensureSession() {
        if (localStorage.getItem('td_access_token')) return;
        const res = await rawFetch('v1/auth/guest', { method: 'POST' });
        if (!res.ok) throw new Error('Could not start session');
        const { access_token, refresh_token } = await res.json();
        localStorage.setItem('td_access_token', access_token);
        localStorage.setItem('td_refresh_token', refresh_token);
        localStorage.setItem('td_is_guest', '1');
    }

    return {
        get:    (path)        => request('GET',    path),
        post:   (path, body)  => request('POST',   path, body),
        patch:  (path, body)  => request('PATCH',  path, body),
        del:    (path)        => request('DELETE', path),
        ensureSession,
        isGuest:    () => localStorage.getItem('td_is_guest') === '1',
        isLoggedIn: () => !!localStorage.getItem('td_access_token') && localStorage.getItem('td_is_guest') !== '1',
        escHtml,
    };
})();
