"""Генератор мрамора для galery.uz: тот же приём, что был в SVG (fractal noise +
узкая полоса значений = прожилка), но считается один раз и сохраняется картинкой.

python3 marble.py <out_dir>
"""
import sys, pathlib
import numpy as np
from PIL import Image

VB_W, VB_H = 1600.0, 1000.0   # координаты, в которых заданы частоты (как viewBox у SVG)


def perlin(xs, ys, rng):
    """2D-градиентный шум Перлина в точках сетки xs × ys. Значения ~[-1, 1]."""
    x0 = np.floor(xs).astype(np.int64); y0 = np.floor(ys).astype(np.int64)
    fx = (xs - x0).astype(np.float32); fy = (ys - y0).astype(np.float32)
    nx, ny = x0.max() + 2 - x0.min(), y0.max() + 2 - y0.min()
    ang = rng.uniform(0, 2 * np.pi, (ny, nx)).astype(np.float32)
    gx, gy = np.cos(ang), np.sin(ang)
    ix = x0 - x0.min(); iy = y0 - y0.min()
    IX, IY = np.meshgrid(ix, iy); FX, FY = np.meshgrid(fx, fy)

    def dot(ox, oy):
        return gx[IY + oy, IX + ox] * (FX - ox) + gy[IY + oy, IX + ox] * (FY - oy)

    fade = lambda t: t * t * t * (t * (t * 6 - 15) + 10)
    u, v = fade(FX), fade(FY)
    a = dot(0, 0) + u * (dot(1, 0) - dot(0, 0))
    b = dot(0, 1) + u * (dot(1, 1) - dot(0, 1))
    return (a + v * (b - a)) * 1.41


def fractal(w, h, fx, fy, octaves, seed):
    """Аналог feTurbulence type=fractalNoise: сумма октав, результат в [0..1] около 0.5."""
    rng = np.random.default_rng(seed)
    sx, sy = VB_W / w, VB_H / h                  # пиксель → единицы viewBox
    xs = np.arange(w, dtype=np.float64) * sx
    ys = np.arange(h, dtype=np.float64) * sy
    total = np.zeros((h, w), np.float32); amp = 1.0; f1, f2 = fx, fy
    for _ in range(octaves):
        total += amp * perlin(xs * f1 + rng.uniform(0, 1000), ys * f2 + rng.uniform(0, 1000), rng)
        amp *= 0.5; f1 *= 2; f2 *= 2
    return np.clip((total + 1) / 2, 0, 1)


def band(n, peak, c, side):
    t = np.zeros(n, np.float32); t[c] = peak; t[c - 1] = side; t[c + 1] = side
    return t


def render(w, h, base, layers):
    img = np.empty((h, w, 3), np.float32); img[:] = np.array(base, np.float32) / 255
    for fx, fy, octv, seed, col, table in layers:
        v = fractal(w, h, fx, fy, octv, seed)
        a = np.interp(v, np.linspace(0, 1, len(table)), table).astype(np.float32)[..., None]
        img = img * (1 - a) + np.array(col, np.float32) * a
    return Image.fromarray((np.clip(img, 0, 1) * 255 + .5).astype(np.uint8))


DARK = ((0x1b, 0x1a, 0x17), [
    (.0014, .0036, 8, 4,  (.90, .85, .74), band(48, .85, 23, .12)),
    (.0035, .008,  7, 19, (.80, .68, .46), band(48, .45, 24, .05)),
    (.0011, .0028, 8, 31, (.90, .85, .74), band(64, .35, 31, .04)),
])
LIGHT = ((0xf3, 0xed, 0xe3), [
    (.0013, .0034, 8, 8,  (.42, .38, .33), band(48, .70, 23, .10)),
    (.0033, .0075, 7, 23, (.55, .50, .42), band(48, .35, 24, .04)),
])

if __name__ == "__main__":
    out = pathlib.Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
    for name, (base, layers) in {"marble-dark": DARK, "marble-light": LIGHT}.items():
        for w, suffix in ((2560, ""), (3840, "@2x")):
            h = int(w * VB_H / VB_W)
            im = render(w, h, base, layers)
            im.save(out / f"{name}{suffix}.webp", "WEBP", quality=88, method=6)
            if not suffix:
                im.save(out / f"{name}.jpg", "JPEG", quality=88, optimize=True, progressive=True)
            print(name, suffix or "1x", w, h)
    # зерно для фона страницы: маленькая бесшовная плитка
    rng = np.random.default_rng(5)
    g = rng.normal(0, 1, (160, 160)).astype(np.float32)
    alpha = np.clip(np.abs(g) * 9, 0, 22).astype(np.uint8)
    tile = np.zeros((160, 160, 4), np.uint8); tile[..., 0] = 77; tile[..., 1] = 64; tile[..., 2] = 51; tile[..., 3] = alpha
    Image.fromarray(tile, "RGBA").save(out / "grain.png", optimize=True)
