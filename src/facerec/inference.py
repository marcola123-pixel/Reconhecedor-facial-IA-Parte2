"""Carregamento seguro de modelos e geração de embeddings."""

from __future__ import annotations

import hashlib
import json

from pathlib import Path
from typing import List, Tuple

import numpy as np
import torch
from PIL import Image

from .data import build_transform
from .models import build_model


def run_fingerprint(run_dir: str | Path) -> str:
    """
    Gera um identificador baseado nos metadados e no checkpoint.
    Se o modelo mudar, a identificação também muda.
    """

    run_dir = Path(run_dir)

    meta_path = run_dir / "meta.json"
    checkpoint_path = run_dir / "best.pt"

    if not meta_path.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {meta_path}")

    if not checkpoint_path.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {checkpoint_path}")

    digest = hashlib.sha256()

    digest.update(meta_path.read_bytes())

    with checkpoint_path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)

    return digest.hexdigest()



def load_run(
    run_dir: str | Path,
    device: str = "cpu"
) -> Tuple[torch.nn.Module, dict, object]:

    run_dir = Path(run_dir)

    meta = json.loads(
        (run_dir / "meta.json").read_text(encoding="utf-8")
    )

    model = build_model(
        meta["model"],
        meta["image_size"],
        load_pretrained=False
    )

    checkpoint = torch.load(
        run_dir / "best.pt",
        map_location=device,
        weights_only=True
    )

    # A arquitetura atual usa FaceNet sem cabeça de classificação.
    # O checkpoint pode conter os pesos auxiliares da camada logits.
    logits_keys = [
        key for key in checkpoint
        if key in {
            "backbone.logits.weight",
            "backbone.logits.bias"
        }
    ]

    for key in logits_keys:
        del checkpoint[key]

    # Verifica se todos os pesos restantes correspondem à arquitetura.
    model.load_state_dict(checkpoint, strict=True)

    model.to(device)
    model.eval()

    transform = build_transform(
        meta["image_size"],
        train=False
    )

    return model, meta, transform



@torch.no_grad()
def embed_images(
    model,
    transform,
    images: List[Image.Image],
    device: str = "cpu"
) -> np.ndarray:

    if not images:
        raise ValueError("Nenhuma imagem foi fornecida.")

    tensors = [
        transform(image.convert("RGB"))
        for image in images
    ]

    batch = torch.stack(tensors).to(device)

    embeddings = model.eval()(batch)

    embeddings = embeddings.detach().cpu().numpy()
    embeddings = embeddings.astype(np.float64)

    if embeddings.ndim != 2:
        raise ValueError("O modelo não retornou embeddings 2D.")

    if not np.all(np.isfinite(embeddings)):
        raise ValueError("O modelo gerou embeddings inválidos.")

    norms = np.linalg.norm(embeddings, axis=1)

    if np.any(norms < 1e-12):
        raise ValueError("O modelo gerou embedding com norma zero.")

    return embeddings