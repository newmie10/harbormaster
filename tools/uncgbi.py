#!/usr/bin/env python3
"""Convert Apple CgBI ("iPhone-optimized") PNGs into standard PNGs.

CgBI differences: extra CgBI chunk before IHDR, IDAT is raw deflate (no zlib
header/adler), pixels are BGRA with premultiplied alpha.

Usage: uncgbi.py SRC_DIR DST_DIR   (non-CgBI PNGs are copied unchanged)
"""
import struct
import sys
import zlib
from pathlib import Path

from PIL import Image

SIG = b"\x89PNG\r\n\x1a\n"


def chunks(data):
    pos = 8
    while pos < len(data):
        (length,) = struct.unpack(">I", data[pos : pos + 4])
        ctype = data[pos + 4 : pos + 8]
        yield ctype, data[pos + 8 : pos + 8 + length]
        pos += 12 + length


def unfilter(raw, width, height, bpp=4):
    stride = width * bpp
    out = bytearray(stride * height)
    prev = bytearray(stride)
    pos = 0
    for y in range(height):
        ftype = raw[pos]
        line = bytearray(raw[pos + 1 : pos + 1 + stride])
        pos += 1 + stride
        if ftype == 1:
            for i in range(bpp, stride):
                line[i] = (line[i] + line[i - bpp]) & 0xFF
        elif ftype == 2:
            for i in range(stride):
                line[i] = (line[i] + prev[i]) & 0xFF
        elif ftype == 3:
            for i in range(stride):
                left = line[i - bpp] if i >= bpp else 0
                line[i] = (line[i] + ((left + prev[i]) >> 1)) & 0xFF
        elif ftype == 4:
            for i in range(stride):
                a = line[i - bpp] if i >= bpp else 0
                b = prev[i]
                c = prev[i - bpp] if i >= bpp else 0
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                pred = a if pa <= pb and pa <= pc else (b if pb <= pc else c)
                line[i] = (line[i] + pred) & 0xFF
        out[y * stride : (y + 1) * stride] = line
        prev = line
    return bytes(out)


ADAM7 = [(0, 0, 8, 8), (4, 0, 8, 8), (0, 4, 4, 8), (2, 0, 4, 4), (0, 2, 2, 4), (1, 0, 2, 2), (0, 1, 1, 2)]


def deinterlace(raw, width, height, bpp=4):
    out = bytearray(width * height * bpp)
    pos = 0
    for x0, y0, dx, dy in ADAM7:
        pw = (width - x0 + dx - 1) // dx
        ph = (height - y0 + dy - 1) // dy
        if pw <= 0 or ph <= 0:
            continue
        size = ph * (1 + pw * bpp)
        sub = unfilter(raw[pos : pos + size], pw, ph, bpp)
        pos += size
        for py in range(ph):
            for px in range(pw):
                s = (py * pw + px) * bpp
                d = ((y0 + py * dy) * width + x0 + px * dx) * bpp
                out[d : d + bpp] = sub[s : s + bpp]
    return bytes(out)


def convert(src: Path, dst: Path) -> bool:
    data = src.read_bytes()
    if data[:8] != SIG or data[12:16] != b"CgBI":
        dst.write_bytes(data)
        return False
    idat = bytearray()
    width = height = None
    for ctype, body in chunks(data):
        if ctype == b"IHDR":
            width, height, depth, color, _, _, interlace = struct.unpack(">IIBBBBB", body)
            if depth != 8 or color != 6:
                raise ValueError(f"{src}: unsupported IHDR depth={depth} color={color}")
        elif ctype == b"IDAT":
            idat += body
    raw = zlib.decompress(bytes(idat), -15)
    pixels = deinterlace(raw, width, height) if interlace else unfilter(raw, width, height)
    img = Image.frombytes("RGBA", (width, height), pixels)
    b, g, r, a = img.split()
    img = Image.merge("RGBA", (r, g, b, a))
    # Un-premultiply alpha.
    px = bytearray(img.tobytes())
    for i in range(0, len(px), 4):
        alpha = px[i + 3]
        if 0 < alpha < 255:
            for c in range(3):
                px[i + c] = min(255, px[i + c] * 255 // alpha)
    Image.frombytes("RGBA", (width, height), bytes(px)).save(dst)
    return True


def main():
    src_dir, dst_dir = Path(sys.argv[1]), Path(sys.argv[2])
    dst_dir.mkdir(parents=True, exist_ok=True)
    converted = 0
    for src in sorted(src_dir.glob("*.png")):
        converted += convert(src, dst_dir / src.name)
    print(f"converted {converted} CgBI PNGs into {dst_dir}")


if __name__ == "__main__":
    main()
