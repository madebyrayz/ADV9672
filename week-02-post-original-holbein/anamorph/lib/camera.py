"""Pinhole camera matching viewer.js (lookAt with world 'down' = +y in the SHARP frame)."""
import numpy as np


def look_at(pos, target):
    pos, target = np.asarray(pos, float), np.asarray(target, float)
    f = target - pos; f /= np.linalg.norm(f)
    r = np.cross([0, 1, 0], f); r = r / (np.linalg.norm(r) or 1)
    d = np.cross(f, r)
    return r, d, f


def project(pos, target, fratio, size, pts):
    """3D points (N,3) -> pixel (N,2) in a size x size render with focal = fratio*size; also returns depth."""
    r, d, f = look_at(pos, target)
    P = np.atleast_2d(np.asarray(pts, float)) - np.asarray(pos, float)
    x, y, z = P @ r, P @ d, P @ f
    fpx = fratio * size
    with np.errstate(divide="ignore", invalid="ignore"):
        u = size / 2 + fpx * x / z; v = size / 2 + fpx * y / z
    return np.stack([u, v], 1), z
