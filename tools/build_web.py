# -*- coding: utf-8 -*-
"""
Build ban web (WebAssembly) bang pygbag -> build/web_app/build/web/ (index.html + tdcaro.apk)

    pip install pygbag
    python tools/build_web.py            # build
    python tools/build_web.py --serve    # build + chay thu tai http://localhost:8000

GitHub Actions (.github/workflows/web.yml) chay script nay roi dang len GitHub Pages.
"""
import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP = os.path.join(ROOT, 'build', 'web_app')
SRC_FILES = ['Finals.py', 'ai_engine_v2.py', 'online.py', 'relay.py', 'updater.py', 'shortcuts.py']


def main():
    if os.path.isdir(APP):
        shutil.rmtree(APP)
    os.makedirs(os.path.join(APP, 'src'))
    for f in SRC_FILES:
        shutil.copy2(os.path.join(ROOT, 'src', f), os.path.join(APP, 'src', f))
    shutil.copy2(os.path.join(ROOT, 'web', 'main.py'), os.path.join(APP, 'main.py'))
    a = os.path.join(APP, 'assets')
    os.makedirs(a)
    shutil.copy2(os.path.join(ROOT, 'assets', 'icon.png'), a)
    shutil.copy2(os.path.join(ROOT, 'assets', 'icon.png'), os.path.join(APP, 'favicon.png'))
    # nhac KHONG dong goi vao game: trinh duyet tai rieng tung bai khi phat (goi tai nho hon nhieu)
    shutil.copytree(os.path.join(ROOT, 'assets', 'fonts'), os.path.join(a, 'fonts'))
    args = [sys.executable, '-m', 'pygbag', '--title', 'TD Caro', '--app_name', 'tdcaro', '--width', '1280', '--height', '800',
            '--template', os.path.join(ROOT, 'web', 'tdcaro.tmpl')]
    if '--serve' not in sys.argv:
        args.append('--build')
    args.append(APP)
    print(' '.join(args))
    subprocess.check_call(args, cwd=ROOT)
    out = os.path.join(APP, 'build', 'web')
    shutil.copy2(os.path.join(ROOT, 'assets', 'icon.png'), os.path.join(out, 'favicon.png'))
    shutil.copytree(os.path.join(ROOT, 'assets', 'music'), os.path.join(out, 'music'), dirs_exist_ok=True)
    for extra in ('web_app.apk',):            # GitHub Pages chi can .tar.gz (.apk danh cho itch.io)
        if os.path.exists(os.path.join(out, extra)):
            os.remove(os.path.join(out, extra))
    # ten goi game kem phien ban -> trinh duyet khong dung nham ban cu trong bo nho dem
    import re
    src = open(os.path.join(ROOT, 'src', 'Finals.py'), encoding='utf-8').read()
    ver = re.search(r"^APP_VERSION = '([^']+)'", src, re.M).group(1)
    stamp = f'{ver}-{int(os.path.getmtime(os.path.join(APP, "src", "Finals.py")))}'
    new_name = f'web_app-{stamp}.tar.gz'
    os.replace(os.path.join(out, 'web_app.tar.gz'), os.path.join(out, new_name))
    idx = os.path.join(out, 'index.html')
    html = open(idx, encoding='utf-8').read()
    assert 'web_app.tar.gz' in html
    open(idx, 'w', encoding='utf-8').write(html.replace('web_app.tar.gz', new_name))
    print('\nBan web:', out)
    for f in sorted(os.listdir(out)):
        print(f'  {f:<24} {os.path.getsize(os.path.join(out, f)) / 1e6:6.2f} MB')


if __name__ == '__main__':
    main()
