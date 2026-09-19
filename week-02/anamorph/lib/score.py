"""Skull-region scoring shared by Phase 1 (analytic perspective) and Phase 2/4 (SHARP renders).

Three scores, reported separately, never blended:
  clip_skull   : CLIP (ViT-B-32, laion2b) softmax probability of "a human skull" against negatives.
  clip_sim     : raw cosine similarity to the skull prompt (for reference).
  symmetry     : bilateral (left-right) symmetry of the crop, 1 - mean|I - flip(I)| / mean|I|.
                 NOTE a correctly resolved skull is a PROFILE, so symmetry is not expected to peak
                 at the solution; it is reported because the brief asked for it as a cross-check.
"""

from __future__ import annotations

import numpy as np
import torch
from PIL import Image

POS = ["a photo of a human skull", "a painting of a skull", "a skull in profile"]
NEG = ["a distorted smeared shape", "an abstract streak of paint", "a blurry unrecognisable object",
       "a mosaic floor", "a bone-coloured smear", "a painting of a stick"]

_model = None


def _load(device):
    global _model
    if _model is None:
        import open_clip
        model, _, pre = open_clip.create_model_and_transforms("ViT-B-32", pretrained="laion2b_s34b_b79k")
        model = model.eval().to(device)
        tok = open_clip.get_tokenizer("ViT-B-32")
        with torch.no_grad():
            t = model.encode_text(tok(POS + NEG).to(device))
            t = t / t.norm(dim=-1, keepdim=True)
        _model = (model, pre, t)
    return _model


def clip_scores(crops: list[Image.Image], device="mps", batch=128) -> tuple[np.ndarray, np.ndarray]:
    """Returns (p_skull, sim_skull) arrays. p_skull = softmax over POS+NEG at CLIP's logit scale,
    summed over the POS prompts. sim_skull = max cosine similarity over POS prompts."""
    model, pre, text = _load(device)
    ps, sims = [], []
    with torch.no_grad():
        for i in range(0, len(crops), batch):
            x = torch.stack([pre(c.convert("RGB")) for c in crops[i:i + batch]]).to(device)
            f = model.encode_image(x)
            f = f / f.norm(dim=-1, keepdim=True)
            logits = 100.0 * f @ text.T
            prob = logits.softmax(-1)
            ps.append(prob[:, : len(POS)].sum(-1).float().cpu().numpy())
            sims.append((f @ text[: len(POS)].T).max(-1).values.float().cpu().numpy())
    return np.concatenate(ps), np.concatenate(sims)


def symmetry_score(crop: Image.Image) -> float:
    g = np.asarray(crop.convert("L").resize((128, 128)), dtype=np.float32)
    g = g - g.mean()
    d = np.abs(g - g[:, ::-1]).mean()
    return float(1.0 - d / (np.abs(g).mean() * 2 + 1e-6))


_ref_feat = {}


def clip_image_similarity(crops: list[Image.Image], reference: Image.Image, device="mps", batch=128) -> np.ndarray:
    """Cosine similarity of each crop's CLIP image embedding to a reference image (e.g. Boxer's restored skull).
    A stricter perceptual metric than 'skullness': it asks whether the crop looks like THE resolved skull."""
    model, pre, _ = _load(device)
    key = id(reference)
    if key not in _ref_feat:
        with torch.no_grad():
            r = model.encode_image(pre(reference.convert("RGB"))[None].to(device))
            _ref_feat[key] = r / r.norm(dim=-1, keepdim=True)
    ref = _ref_feat[key]
    out = []
    with torch.no_grad():
        for i in range(0, len(crops), batch):
            x = torch.stack([pre(c.convert("RGB")) for c in crops[i:i + batch]]).to(device)
            f = model.encode_image(x); f = f / f.norm(dim=-1, keepdim=True)
            out.append((f @ ref.T)[:, 0].float().cpu().numpy())
    return np.concatenate(out)
