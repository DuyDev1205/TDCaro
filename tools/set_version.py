# -*- coding: utf-8 -*-
"""Ghi so phien ban vao Finals.py (dung trong CI khi build theo tag).  python tools/set_version.py 1.2.3"""
import os
import re
import sys

path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'Finals.py')
ver = sys.argv[1]
src = open(path, encoding='utf-8').read()
src, n = re.subn(r"^APP_VERSION = '[^']*'", f"APP_VERSION = '{ver}'", src, flags=re.M)
assert n == 1, 'APP_VERSION not found'
open(path, 'w', encoding='utf-8').write(src)
print('APP_VERSION =', ver)
