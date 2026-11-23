"""Decrypt / encrypt TRIANGLE STRATEGY (PC) .lub Lua 5.1 bytecode.

The PC build XORs each .lub with a fixed 256-byte repeating key (lub_key.bin),
starting at a per-file offset. Decrypt finds the offset from the known Lua header.

  python lubcrypt.py dec <in.lub> <out.luac>
  python lubcrypt.py enc <in.luac> <out.lub> <offset>   (offset 0-255; reuse the original file's)
  python lubcrypt.py offset <in.lub>                     (print the file's key offset)
"""
import sys, os

KEY = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'lub_key.bin'), 'rb').read()
HDR = b'\x1bLua\x51\x00\x01\x04\x08\x04\x08\x00'


def xor(data, off):
    return bytes(b ^ KEY[(off + i) % 256] for i, b in enumerate(data))


def find_offset(data):
    for o in range(256):
        if xor(data[:12], o) == HDR:
            return o
    raise ValueError('not a recognised .lub')


if __name__ == '__main__':
    cmd = sys.argv[1]
    data = open(sys.argv[2], 'rb').read()
    if cmd == 'offset':
        print(find_offset(data))
    elif cmd == 'dec':
        open(sys.argv[3], 'wb').write(xor(data, find_offset(data)))
    elif cmd == 'enc':
        open(sys.argv[3], 'wb').write(xor(data, int(sys.argv[4])))
