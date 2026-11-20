"""Alinhamento geometrico facial por cinco landmarks."""

from __future__ import annotations

import numpy as np
from PIL import Image


# Referencia ArcFace 112x112, adaptada para 160x160.
REFERENCE_112 = np.array(
    [
        [38.2946, 51.6963],
        [73.5318, 51.5014],
        [56.0252, 71.7366],
        [41.5493, 92.3655],
        [70.7299, 92.2041],
    ],
    dtype=np.float64,
)


def reference_landmarks(image_size: int = 160) -> np.ndarray:
    """Retorna os cinco pontos de referencia para a resolucao escolhida."""

    if image_size <= 0:
        raise ValueError("image_size deve ser positivo.")

    return REFERENCE_112 * (image_size / 112.0)


def estimate_similarity(
    source: np.ndarray,
    target: np.ndarray,
) -> np.ndarray:
    """Estima uma transformacao de similaridade 2D sem reflexao."""

    source = np.asarray(source, dtype=np.float64)
    target = np.asarray(target, dtype=np.float64)

    if source.shape != (5, 2) or target.shape != (5, 2):
        raise ValueError("Esperados cinco landmarks com coordenadas (x, y).")

    if not np.isfinite(source).all() or not np.isfinite(target).all():
        raise ValueError("Landmarks contem valores invalidos.")

    source_center = source.mean(axis=0)
    target_center = target.mean(axis=0)

    source_zero = source - source_center
    target_zero = target - target_center

    variance = np.sum(source_zero ** 2)

    if variance < 1e-10:
        raise ValueError("Landmarks degenerados.")

    covariance = source_zero.T @ target_zero

    u, _, vt = np.linalg.svd(covariance)

    correction = np.eye(2)

    if np.linalg.det(u @ vt) < 0:
        correction[-1, -1] = -1

    rotation = u @ correction @ vt

    scale = np.sum(
        (source_zero @ rotation) * target_zero
    ) / variance

    if not np.isfinite(scale) or scale <= 1e-10:
        raise ValueError("Escala invalida para alinhamento.")

    linear = scale * rotation
    translation = target_center - source_center @ linear

    matrix = np.eye(3, dtype=np.float64)
    matrix[:2, :2] = linear
    matrix[2, :2] = translation

    return matrix


def align_face(
    image: Image.Image,
    landmarks: np.ndarray,
    image_size: int = 160,
) -> Image.Image:
    """Alinha o rosto e retorna uma imagem RGB."""

    if image_size <= 0:
        raise ValueError("image_size deve ser positivo.")

    source = np.asarray(landmarks, dtype=np.float64)
    target = reference_landmarks(image_size)

    matrix = estimate_similarity(source, target)

    # Pillow usa mapeamento inverso: destino -> origem.
    inverse = np.linalg.inv(matrix)

    # A matriz acima utiliza coordenadas como vetores-linha.
    # Para Pillow, x_origem e y_origem sao calculados
    # a partir das coordenadas de destino.
    coefficients = (
        float(inverse[0, 0]),
        float(inverse[1, 0]),
        float(inverse[2, 0]),
        float(inverse[0, 1]),
        float(inverse[1, 1]),
        float(inverse[2, 1]),
    )

    return image.convert("RGB").transform(
        (image_size, image_size),
        Image.Transform.AFFINE,
        coefficients,
        resample=Image.Resampling.BILINEAR,
    )
