'use strict';

const Auth = (() => {

    const AVATAR_EMOJI = {
        numbers: '🔢', words: '🔤', friend: '👥', flex: '💪', taunt: '😏',
        owl: '🦉', eight: '8️⃣', meta: '♾️', queen: '👑', santa: '🎅',
        sunglasses: '😎', bullseye: '🎯', fire: '🔥', bolt_icon: '⚡',
        star_icon: '⭐', shield: '🛡️', coffee: '☕', anchor: '⚓',
        heart: '❤️', music: '🎵', snowflake: '❄️', sun_icon: '☀️',
        lotus: '🌸', pizza: '🍕', cake: '🎂', egg: '🥚', raven: '🐦',
    };

    const AVATAR_COLOR = {
        red: '#D32F2F', green: '#388E3C', blue: '#1565C0', orange: '#E65100',
        gold: '#FFAA00', black: '#212121', silver: '#C0C0C0', purple: '#7B1FA2',
        teal: '#00695C', pink: '#E91E63', lime: '#558B2F',
    };

    function setNavAvatar(profileLink, avatarId, colorId, displayName) {
        const emoji = avatarId && AVATAR_EMOJI[avatarId];
        const bg = colorId && AVATAR_COLOR[colorId];
        if (bg) profileLink.style.background = bg;
        if (emoji) {
            profileLink.innerHTML = `<span style="font-size:1.2rem;line-height:1">${emoji}</span>`;
        } else {
            const initials = (displayName || '?').split(' ').map(w => w[0]).join('').slice(0, 2).toUpperCase();
            profileLink.innerHTML = `<span style="font-size:0.72rem;font-weight:700;color:${bg ? '#fff' : 'var(--ink-mid)'}">${API.escHtml(initials)}</span>`;
        }
    }

    function saveTokens({ access_token, refresh_token }) {
        localStorage.setItem('td_access_token', access_token);
        localStorage.setItem('td_refresh_token', refresh_token);
        localStorage.removeItem('td_is_guest');
    }

    async function updateNav() {
        const profileLink = document.getElementById('nav-profile-link');
        const devLink = document.getElementById('nav-dev-link');

        if (API.isLoggedIn()) {
            // Show initials immediately from localStorage so the icon never disappears
            if (profileLink) {
                const name = localStorage.getItem('td_display_name') || '';
                if (name) setNavAvatar(profileLink, null, null, name);
            }
            // Then fetch full profile to upgrade to emoji + colour
            try {
                const profile = await API.get('v1/users/me');
                if (profileLink) {
                    setNavAvatar(profileLink, profile.avatar_id, profile.avatar_color_id, profile.display_name);
                }
                if (devLink && profile && profile.is_developer) {
                    devLink.style.display = '';
                }
            } catch (_) { /* keep initials already shown */ }
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

    async function register(email, password) {
        const guestToken = API.isGuest() ? localStorage.getItem('td_access_token') : null;
        const tokens = await API.post('v1/auth/register', {
            email,
            password,
            guest_access_token: guestToken,
        });
        saveTokens(tokens);
        const profile = await API.get('v1/users/me');
        localStorage.setItem('td_display_name', profile.display_name);
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
