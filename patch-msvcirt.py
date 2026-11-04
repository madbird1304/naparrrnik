#!/usr/bin/env python3
"""Make wine's msvcirt.dll write the NUL terminator the voice engine relies on.

The engine reuses one ostrstream for all sentences and ends each with `<< ends`,
which lands in ostream::operator<<(unsigned char). Wine's version takes the
length with strlen, so a NUL is never written: the engine then reads on into the
leftovers of the previous sentence and speaks them ("3 что", repeated words).

ostream::put(char) has the same calling convention and writes the byte as is, so
point the export there. Only that export changes. The engine only ever passes 0
to this operator, so losing its width padding does not matter.

usage: patch-msvcirt.py SRC_DLL DST_DLL
"""
import struct
import sys

src, dst = sys.argv[1:3]
image = bytearray(open(src, 'rb').read())

pe = struct.unpack_from('<I', image, 0x3c)[0]
sections, opt_size = struct.unpack_from('<H', image, pe + 6)[0], struct.unpack_from('<H', image, pe + 20)[0]
opt = pe + 24
assert struct.unpack_from('<H', image, opt)[0] == 0x10b, 'expected a 32-bit PE'
table = [struct.unpack_from('<8sIIII', image, opt + opt_size + i * 40) for i in range(sections)]


def offset(rva):
    for _, vsize, va, rsize, raw in table:
        if va <= rva < va + max(vsize, rsize):
            return rva - va + raw
    raise ValueError(hex(rva))


exports = offset(struct.unpack_from('<I', image, opt + 96)[0])
_, name_count, functions, names, ordinals = struct.unpack_from('<IIIII', image, exports + 20)
ordinal_of = {}
for i in range(name_count):
    start = offset(struct.unpack_from('<I', image, offset(names) + 4 * i)[0])
    name = image[start:image.index(0, start)].decode()
    ordinal_of[name] = struct.unpack_from('<H', image, offset(ordinals) + 2 * i)[0]

slot = offset(functions) + 4 * ordinal_of['??6ostream@@QAEAAV0@E@Z']
put = struct.unpack_from('<I', image, offset(functions) + 4 * ordinal_of['?put@ostream@@QAEAAV1@D@Z'])[0]
struct.pack_into('<I', image, slot, put)

# Without this marker wine treats the file as a real native DLL and loads it.
marker = b'Wine builtin DLL'
start = image.index(marker)
image[start:start + len(marker)] = bytes(len(marker))

open(dst, 'wb').write(image)
