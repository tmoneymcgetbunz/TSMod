"""Pure-Python AES-256 ECB decryption, used by tspak.py when pycryptodome isn't installed (e.g. a stock Steam Deck).

Decryption only (the pak reader never encrypts). Table-driven (T-tables), so a few MB per second on CPython; the
editor reads the game's tables once and caches them. Checked against pycryptodome (tools/aes_py.py selftest).
"""
import struct

_SBOX = [0] * 256
_INV = [0] * 256


def _init():
    p = q = 1
    while True:
        p = p ^ ((p << 1) & 0xFF) ^ (0x1B if p & 0x80 else 0)
        q ^= q << 1; q ^= q << 2; q ^= q << 4; q &= 0xFF
        if q & 0x80: q ^= 0x09
        x = q ^ ((q << 1) | (q >> 7)) & 0xFF ^ ((q << 2) | (q >> 6)) & 0xFF ^ ((q << 3) | (q >> 5)) & 0xFF \
            ^ ((q << 4) | (q >> 4)) & 0xFF
        x = (x ^ 0x63) & 0xFF
        _SBOX[p] = x; _INV[x] = p
        if p == 1: break
    _SBOX[0] = 0x63; _INV[0x63] = 0


_init()


def _xt(a):
    return ((a << 1) ^ 0x1B) & 0xFF if a & 0x80 else a << 1


def _mul(a, b):
    r = 0
    while b:
        if b & 1: r ^= a
        a = _xt(a); b >>= 1
    return r


# Inverse T-tables: TD0[x] = (14·s, 9·s, 13·s, 11·s) of s = InvSbox[x], packed big-endian; TD1..3 are byte rotations.
_TD = [[0] * 256 for _ in range(4)]
for _x in range(256):
    _s = _INV[_x]
    _w = (_mul(_s, 14) << 24) | (_mul(_s, 9) << 16) | (_mul(_s, 13) << 8) | _mul(_s, 11)
    for _i in range(4):
        _TD[_i][_x] = _w
        _w = ((_w >> 8) | (_w << 24)) & 0xFFFFFFFF
_TD0, _TD1, _TD2, _TD3 = _TD


def _expand(key):
    nk = len(key) // 4; nr = nk + 6
    w = list(struct.unpack('>%dI' % nk, key))
    rcon = 1
    for i in range(nk, 4 * (nr + 1)):
        t = w[i - 1]
        if i % nk == 0:
            t = ((t << 8) | (t >> 24)) & 0xFFFFFFFF
            t = (_SBOX[t >> 24] << 24) | (_SBOX[(t >> 16) & 255] << 16) | (_SBOX[(t >> 8) & 255] << 8) | _SBOX[t & 255]
            t ^= rcon << 24; rcon = _xt(rcon)
        elif nk > 6 and i % nk == 4:
            t = (_SBOX[t >> 24] << 24) | (_SBOX[(t >> 16) & 255] << 16) | (_SBOX[(t >> 8) & 255] << 8) | _SBOX[t & 255]
        w.append(w[i - nk] ^ t)
    return w, nr


def _inv_mix_word(v):
    # InvMixColumns on a round-key word: TD lookup of Sbox[byte] undoes the InvSbox inside the table.
    return (_TD0[_SBOX[v >> 24]] ^ _TD1[_SBOX[(v >> 16) & 255]] ^ _TD2[_SBOX[(v >> 8) & 255]] ^ _TD3[_SBOX[v & 255]])


class AES256Decryptor:
    def __init__(self, key):
        w, nr = _expand(key)
        self.nr = nr
        rk = [w[4 * r:4 * r + 4] for r in range(nr + 1)]
        # Equivalent inverse cipher: reversed round keys, InvMixColumns applied to the middle ones.
        self.dk = [rk[nr]] + [[_inv_mix_word(v) for v in rk[r]] for r in range(nr - 1, 0, -1)] + [rk[0]]

    def decrypt(self, data):
        if len(data) % 16: raise ValueError('data length must be a multiple of 16')
        out = bytearray(len(data))
        dk, nr = self.dk, self.nr
        T0, T1, T2, T3, IS = _TD0, _TD1, _TD2, _TD3, _INV
        k0 = dk[0]
        for off in range(0, len(data), 16):
            s0, s1, s2, s3 = struct.unpack_from('>4I', data, off)
            s0 ^= k0[0]; s1 ^= k0[1]; s2 ^= k0[2]; s3 ^= k0[3]
            for r in range(1, nr):
                k = dk[r]
                t0 = T0[s0 >> 24] ^ T1[(s3 >> 16) & 255] ^ T2[(s2 >> 8) & 255] ^ T3[s1 & 255] ^ k[0]
                t1 = T0[s1 >> 24] ^ T1[(s0 >> 16) & 255] ^ T2[(s3 >> 8) & 255] ^ T3[s2 & 255] ^ k[1]
                t2 = T0[s2 >> 24] ^ T1[(s1 >> 16) & 255] ^ T2[(s0 >> 8) & 255] ^ T3[s3 & 255] ^ k[2]
                t3 = T0[s3 >> 24] ^ T1[(s2 >> 16) & 255] ^ T2[(s1 >> 8) & 255] ^ T3[s0 & 255] ^ k[3]
                s0, s1, s2, s3 = t0, t1, t2, t3
            k = dk[nr]
            struct.pack_into('>4I', out, off,
                             ((IS[s0 >> 24] << 24) | (IS[(s3 >> 16) & 255] << 16) | (IS[(s2 >> 8) & 255] << 8) | IS[s1 & 255]) ^ k[0],
                             ((IS[s1 >> 24] << 24) | (IS[(s0 >> 16) & 255] << 16) | (IS[(s3 >> 8) & 255] << 8) | IS[s2 & 255]) ^ k[1],
                             ((IS[s2 >> 24] << 24) | (IS[(s1 >> 16) & 255] << 16) | (IS[(s0 >> 8) & 255] << 8) | IS[s3 & 255]) ^ k[2],
                             ((IS[s3 >> 24] << 24) | (IS[(s2 >> 16) & 255] << 16) | (IS[(s1 >> 8) & 255] << 8) | IS[s0 & 255]) ^ k[3])
        return bytes(out)


if __name__ == '__main__':                     # selftest: python tools/aes_py.py
    import os, time
    from Crypto.Cipher import AES
    key = os.urandom(32); data = os.urandom(16 * 4096)
    ct = AES.new(key, AES.MODE_ECB).encrypt(data)
    t = time.time(); pt = AES256Decryptor(key).decrypt(ct); dt = time.time() - t
    # FIPS-197 C.3 vector
    k = bytes(range(32)); c = bytes.fromhex('8ea2b7ca516745bfeafc49904b496089')
    assert AES256Decryptor(k).decrypt(c) == bytes.fromhex('00112233445566778899aabbccddeeff')
    print('random 64 KiB match:', pt == data, f'({len(data) / dt / 1e6:.2f} MB/s)', '| FIPS-197 vector OK')
