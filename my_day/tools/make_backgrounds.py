"""Draws My Day's built-in backgrounds (static/src/img/bg_*.jpg).

Run from the module folder: python3 tools/make_backgrounds.py
Soft, unbranded scenes; cards sit on top, so they stay calm and low-detail.
"""
import numpy as np
from PIL import Image, ImageFilter

W, H = 1920, 1200
rng = np.random.default_rng(7)
y, x = np.mgrid[0:H, 0:W].astype(np.float32)
u, v = x / W, y / H


def rgb(hex_):
    return np.array([int(hex_[i:i + 2], 16) for i in (1, 3, 5)], np.float32)


def vertical(top, bottom):
    t = v[..., None]
    return rgb(top) * (1 - t) + rgb(bottom) * t


def glow(img, cx, cy, r, color, strength=1.0):
    d = ((u - cx) ** 2 + ((v - cy) * H / W) ** 2) / (r * r)
    a = (np.exp(-d) * strength)[..., None]
    return img * (1 - a) + rgb(color) * a


def band(img, curve, width, color, strength=1.0, soft=1.0):
    """A soft-edged layer below `curve` (a function of u giving v)."""
    edge = curve(u)
    a = np.clip((v - edge) / (width * soft) + 0.5, 0, 1)[..., None] * strength
    return img * (1 - a) + rgb(color) * a


def finish(img, name, grain=3.0, blur=1.2):
    img = img + rng.normal(0, grain, img.shape[:2])[..., None]
    out = Image.fromarray(np.clip(img, 0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(blur))
    out.save(f'static/src/img/bg_{name}.jpg', quality=80, optimize=True, progressive=True)


def stars(img, count, color='#ffffff', top=0.7):
    for _ in range(count):
        sx, sy = rng.integers(0, W), int(rng.random() ** 1.6 * H * top)
        size = rng.choice([1, 1, 1, 2, 2, 3])
        bright = rng.uniform(0.4, 1.0)
        img[max(sy - size, 0):sy + size, max(sx - size, 0):sx + size] = \
            img[max(sy - size, 0):sy + size, max(sx - size, 0):sx + size] * (1 - bright) + rgb(color) * bright
    return img


# Dawn: a low sun through peach and lilac.
img = vertical('#8e9fd6', '#f6c9a8')
img = glow(img, 0.72, 0.78, 0.35, '#ffe2b8', 0.9)
img = glow(img, 0.2, 0.15, 0.45, '#b6a4dc', 0.6)
img = band(img, lambda s: 0.82 + 0.03 * np.sin(s * 5.0), 0.01, '#c98f8f', 0.55)
img = band(img, lambda s: 0.9 + 0.02 * np.sin(s * 7.0 + 1), 0.01, '#a87686', 0.6)
finish(img, 'dawn')

# Meadow: rolling green hills under a pale sky.
img = vertical('#cfe7f2', '#eef5e0')
img = glow(img, 0.3, 0.2, 0.3, '#ffffff', 0.7)
img = band(img, lambda s: 0.58 + 0.06 * np.sin(s * 3.2 + 0.5), 0.008, '#a9cf8c', 1.0)
img = band(img, lambda s: 0.7 + 0.05 * np.sin(s * 4.1 + 2.2), 0.008, '#7fb26b', 1.0)
img = band(img, lambda s: 0.83 + 0.04 * np.sin(s * 5.3 + 4.0), 0.008, '#5c9358', 1.0)
finish(img, 'meadow')

# Lagoon: turquoise water bands.
img = vertical('#bfe8ef', '#2f8fa6')
img = glow(img, 0.8, 0.1, 0.4, '#f4fbff', 0.8)
for i, (base, col) in enumerate([(0.5, '#7fd0d8'), (0.62, '#58b9c8'), (0.74, '#3ea0b6'), (0.86, '#2a7f99')]):
    img = band(img, lambda s, b=base, k=i: b + 0.018 * np.sin(s * (9 + 3 * k) + k), 0.004, col, 0.75)
finish(img, 'lagoon')

# Dusk: deep indigo to rose with a scatter of stars.
img = vertical('#1d2150', '#b9708c')
img = glow(img, 0.5, 1.05, 0.55, '#f2a07b', 0.75)
img = stars(img, 420)
img = band(img, lambda s: 0.86 + 0.04 * np.sin(s * 2.4 + 1.3), 0.006, '#3a2846', 0.95)
finish(img, 'dusk', blur=0.6)

# Aurora: green and violet ribbons over a night sky.
img = vertical('#071a2b', '#123a45')
img = stars(img, 260, top=0.9)
for cx, col, amp, ph in [(0.42, '#9b7be8', 0.05, 3.1), (0.55, '#4fc3d9', 0.06, 1.7), (0.62, '#38e0a0', 0.08, 0.0)]:
    centre = cx + amp * np.sin(u * 5.5 + ph) + 0.04 * np.sin(u * 13 + ph)
    # A curtain: a bright lower hem that fades upwards, with faint rays.
    above = np.exp(-np.clip(centre - v, 0, None) / 0.16)
    below = np.exp(-(np.clip(v - centre, 0, None) / 0.012) ** 2)
    rays = 0.75 + 0.25 * np.sin(u * 140 + 3 * np.sin(u * 9 + ph))
    a = (np.where(v < centre, above * rays, below) * 0.5)[..., None]
    img = img * (1 - a) + rgb(col) * a
img = band(img, lambda s: 0.88 + 0.03 * np.sin(s * 3.0), 0.005, '#04101a', 1.0)
finish(img, 'aurora', blur=1.6)

# Dunes: warm sand ridges.
img = vertical('#f3dcc0', '#d9a77a')
img = glow(img, 0.75, 0.18, 0.3, '#fff3e0', 0.8)
for base, col, f, ph in [(0.48, '#e6bf95', 2.2, 0.3), (0.6, '#d9a679', 2.9, 1.9), (0.72, '#c98e62', 3.4, 3.3),
                         (0.85, '#b67a51', 4.0, 5.0)]:
    img = band(img, lambda s, b=base, f=f, p=ph: b + 0.07 * np.sin(s * f + p) * np.abs(np.sin(s * 1.3 + p)),
               0.006, col, 1.0)
finish(img, 'dunes')
print('done')
