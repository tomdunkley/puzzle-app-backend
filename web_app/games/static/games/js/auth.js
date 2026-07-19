'use strict';

const Auth = (() => {

    function saveTokens({ access_token, refresh_token }) {
        localStorage.setItem('td_access_token', access_token);
        localStorage.setItem('td_refresh_token', refresh_token);
        localStorage.removeItem('td_is_guest');
    }

    async function updateNav() {
        const profileLink = document.getElementById('nav-profile-link');
        const devLink = document.getElementById('nav-dev-link');

        if (API.isLoggedIn()) {
            // Show initials in the profile circle
            const name = localStorage.getItem('td_display_name') || '';
            if (profileLink && name) {
                const initials = name.split(' ').map(w => w[0]).join('').slice(0, 2).toUpperCase();
                profileLink.innerHTML = `<span style="font-size:0.72rem;font-weight:700;color:var(--ink-mid)">${API.escHtml(initials)}</span>`;
            }
            // Show dev link if developer
            if (devLink) {
                try {
                    const profile = await API.get('v1/users/me');
                    if (profile && profile.is_developer) {
                        devLink.style.display = '';
                    }
                } catch (_) { /* not a dev or request failed */ }
            }
        }

        // Mark active nav link (Puzzles link active on home)
        const path = window.location.pathname.replace(/\/$/, '') || '/';
        document.querySelectorAll('.nav-link').forEach(a => {
            const href = (a.getAttribute('href') || '').replace(/\/$/, '') || '/';
            a.classList.toggle('active', path === href || (href !== '/' && path.startsWith(href)));
        });
    }

    async function login(email, password) {
        const tokens = await API.post('v1/auth/login', { email, password });
        saveTokens(tokens);
        const profile = await API.get('v1/users/me');
        localStorage.setItem('td_display_name', profile.display_name);
        return profile;
    }

    async function register(displayName, email, password) {
        const guestToken = API.isGuest() ? localStorage.getItem('td_access_token') : null;
        const tokens = await API.post('v1/auth/register', {
            display_name: displayName,
            email,
            password,
            guest_access_token: guestToken,
        });
        saveTokens(tokens);
        localStorage.setItem('td_display_name', displayName);
    }

    async function loginWithGoogle(idToken) {
        const guestToken = API.isGuest() ? localStorage.getItem('td_access_token') : null;
        const tokens = await API.post('v1/auth/google', {
            id_token: idToken,
            guest_access_token: guestToken,
        });
        saveTokens(tokens);
        const profile = await API.get('v1/users/me');
        localStorage.setItem('td_display_name', profile.display_name);
        return profile;
    }

    function logout() {
        localStorage.clear();
        window.location.href = '/';
    }

    // Called by Google Sign-In button (global so GIS can invoke it)
    window.handleGoogleSignIn = async (credentialResponse) => {
        const btnEl = document.getElementById('google-signin-btn');
        if (btnEl) btnEl.disabled = true;
        try {
            await loginWithGoogle(credentialResponse.credential);
            window.location.href = localStorage.getItem('td_login_redirect') || '/';
        } catch (e) {
            const errEl = document.getElementById('google-error');
            if (errEl) errEl.textContent = e.message;
            if (btnEl) btnEl.disabled = false;
        }
    };

    document.addEventListener('DOMContentLoaded', () => {
        updateNav();
    });

    return { login, register, loginWithGoogle, logout, saveTokens, updateNav };
})();
