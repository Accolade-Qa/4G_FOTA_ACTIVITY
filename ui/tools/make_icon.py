from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image


def main() -> int:
    if len(sys.argv) < 3:
        print('Usage: python make_icon.py <input_png> <output_ico>')
        return 2

    src = Path(sys.argv[1])
    dst = Path(sys.argv[2])

    if not src.exists():
        print(f'Input not found: {src}')
        return 1

    img = Image.open(src).convert('RGBA')
    sizes = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    img.save(dst, format='ICO', sizes=sizes)
    print(f'Wrote icon: {dst}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
