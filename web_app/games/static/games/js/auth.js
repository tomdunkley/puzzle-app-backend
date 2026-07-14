'use strict';

const Auth = (() => {

    function saveTokens({ access_token, refresh_token }) {
        localStorage.setItem('td_access_token', access_token);
        localStorage.setItem('td_refresh_token', refresh_token);
        localStorage.removeItem('td_is_guest');
    }

    function updateNav() {
        const el = document.getElementById('nav-auth');
        if (!el) return;
        const name = localStorage.getItem('td_display_name');
        if (API.isLoggedIn() && name) {
            el.innerHTML = `
                <span class="nav-user">${API.escHtml(name)}</span>
                <a href="#" class="nav-link" id="logout-btn">Log Out</a>
            `;
            document.getElementById('logout-btn')?.addEventListener('click', e => {
                e.preventDefault();
                logout();
            });
        } else if (!API.isLoggedIn()) {
            el.innerHTML = `
                <a href="/login/" class="nav-link">Log In</a>
                <a href="/register/" class="nav-link nav-cta">Register</a>
            `;
        }
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
        // Mark active nav link
        const path = window.location.pathname.replace(/\/$/, '');
        document.querySelectorAll('.nav-link').forEach(a => {
            const href = a.getAttribute('href')?.replace(/\/$/, '');
            if (href && href !== '' && path.startsWith(href)) {
                a.classList.add('active');
            }
        });
    });

    return { login, register, loginWithGoogle, logout, saveTokens, updateNav };
})();
