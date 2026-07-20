#!/usr/bin/env python3
"""
Renders Django templates to static HTML files, then copies static assets.
Output goes to webapp/web_dist/ ready for `aws s3 sync`.

Run from the webapp/ directory:
    python scripts/build_web.py
"""
import sys
import os
import pathlib
import shutil

# Point Django at web_app/
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent / 'web_app'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'puzzles_web.settings')

import django
django.setup()

from django.test import Client  # noqa: E402 — must come after django.setup()

PAGES = {
    '/':                 'index.html',
    '/words/':           'words/index.html',
    '/numbers/':         'numbers/index.html',
    '/profile/':         'profile/index.html',
    '/dev/':             'dev/index.html',
    '/login/':           'login/index.html',
    '/register/':        'register/index.html',
    '/forgot-password/': 'forgot-password/index.html',
    '/verify-email/':    'verify-email/index.html',
    # /users/<id>/ served by CloudFront rewrite to users/index.html
    '/users/placeholder/': 'users/index.html',
}


def main():
    root = pathlib.Path(__file__).parent.parent
    static_src = root / 'web_app' / 'staticfiles'
    out = root / 'web_dist'

    # Always re-collect static files so JS/CSS source changes are picked up.
    import subprocess
    subprocess.run(
        [sys.executable, 'web_app/manage.py', 'collectstatic', '--noinput'],
        cwd=root, check=True, capture_output=True,
    )

    if out.exists():
        shutil.rmtree(out)
    out.mkdir()

    client = Client()
    ok = True

    for url, filename in PAGES.items():
        response = client.get(url)
        if response.status_code != 200:
            print(f'ERROR {response.status_code}: {url}', file=sys.stderr)
            ok = False
            continue
        dest = out / filename
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(response.content)
        print(f'  {url}  ->  web_dist/{filename}')

    print('Copying static files...')
    shutil.copytree(static_src, out / 'static', dirs_exist_ok=True)

    if not ok:
        sys.exit(1)

    # Netlify rewrite rule: /users/<username>/ → users/index.html (JS handles routing)
    (out / '_redirects').write_text('/users/*  /users/index.html  200\n')

    print(f'\nDone! web_dist/ is ready.')
    print('Deploy with:')
    print('  netlify deploy --prod --dir web_dist/ --site <site-id>')


if __name__ == '__main__':
    main()
