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
    '/leaderboard/':     'leaderboard/index.html',
    '/friends/':         'friends/index.html',
    '/trophies/':        'trophies/index.html',
    '/login/':           'login/index.html',
    '/register/':        'register/index.html',
    '/forgot-password/': 'forgot-password/index.html',
    '/verify-email/':    'verify-email/index.html',
}


def main():
    root = pathlib.Path(__file__).parent.parent
    static_src = root / 'web_app' / 'staticfiles'
    out = root / 'web_dist'

    if not static_src.exists():
        print('ERROR: web_app/staticfiles/ not found.', file=sys.stderr)
        print('Run first:  cd web_app && python manage.py collectstatic --noinput', file=sys.stderr)
        sys.exit(1)

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
        print(f'  {url}  →  web_dist/{filename}')

    print('Copying static files...')
    shutil.copytree(static_src, out / 'static', dirs_exist_ok=True)

    if not ok:
        sys.exit(1)

    print(f'\nDone! web_dist/ is ready.')
    print('Deploy with:')
    print('  aws s3 sync web_dist/ s3://<bucket-name>/ --delete --profile td-puzzles')
    print('  aws cloudfront create-invalidation --distribution-id <id> --paths "/*" --profile td-puzzles')


if __name__ == '__main__':
    main()
