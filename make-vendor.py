#!/usr/bin/env python3
"""Build vendor/*.tar.gz (not in git) from a working wine prefix and balcon dir.

usage: make-vendor.py PREFIX_DIR BALCON_DIR OLD_PREFIX_PATH
OLD_PREFIX_PATH is the path the prefix was installed at: winetricks left
absolute symlinks to it, so they must become relative to survive the move.
"""
import os, pathlib, shutil, subprocess, sys, tempfile

prefix, balcon, old = sys.argv[1:4]
old = os.path.normpath(old)
vendor = pathlib.Path('vendor')
vendor.mkdir(exist_ok=True)

with tempfile.TemporaryDirectory(dir='.') as tmp:
    dst = pathlib.Path(tmp, 'wineprefix').resolve()
    shutil.copytree(prefix, dst, symlinks=True)
    fixed = dropped = 0
    for root, dirs, files in os.walk(dst):
        for name in dirs + files:
            link = pathlib.Path(root, name)
            if not link.is_symlink():
                continue
            target = os.path.normpath(os.readlink(link))
            if target == old or target.startswith(old + '/'):
                real = dst / os.path.relpath(target, old).replace('dosdevices/c:', 'drive_c', 1)
                link.unlink()
                link.symlink_to(os.path.relpath(real, link.parent))
                fixed += 1
            elif target.startswith('/home/'):
                link.unlink()  # desktop links into the old home
                dropped += 1
    print(f'symlinks fixed={fixed} dropped={dropped}')
    broken = [str(p) for p in dst.rglob('*') if p.is_symlink() and not p.exists() and '/dosdevices/' not in str(p)]
    print('broken left:', broken[:10])
    subprocess.check_call(['tar', 'czf', str(vendor.resolve() / 'wineprefix.tar.gz'),
                           '--owner=0', '--group=0', '-C', tmp, 'wineprefix'])

subprocess.check_call(['tar', 'czf', str(vendor / 'balcon.tar.gz'), '--owner=0', '--group=0',
                       '--exclude=readme.*', '-C', str(pathlib.Path(balcon).parent),
                       pathlib.Path(balcon).name])
