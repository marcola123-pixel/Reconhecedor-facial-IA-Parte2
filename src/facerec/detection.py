
"""Detecção e recorte facial com MTCNN.

Aceita somente imagens com exatamente um rosto.
Imagens sem rosto ou com múltiplos rostos são rejeitadas.
"""

from __future__ import annotations

from typing import Optional

import numpy as np
from PIL import Image


class MultipleFacesError(ValueError):
    """Indica que a imagem contém mais de um rosto."""


class FaceDetector:

    def __init__(
        self,
        image_size: int = 160,
        margin: int = 20,
        device: Optional[str] = None
    ):
        from facenet_pytorch import MTCNN

        self.mtcnn = MTCNN(
            image_size=image_size,
            margin=margin,
            post_process=False,
            keep_all=True,
            select_largest=False,
            device=device
        )

    def crop(self, img: Image.Image) -> Optional[Image.Image]:
        """Retorna o rosto recortado em PIL RGB."""

        img = img.convert("RGB")

        # Detecta todos os rostos.
        boxes, probabilities = self.mtcnn.detect(img)

        if boxes is None or len(boxes) == 0:
            return None

        if len(boxes) > 1:
            raise MultipleFacesError(
                f"Foram detectados {len(boxes)} rostos. "
                "Envie uma imagem contendo apenas uma pessoa."
            )

        # Extrai o único rosto detectado.
        face = self.mtcnn.extract(img, boxes, None)

        if face is None:
            return None

        if face.is_sparse:
            face = face.to_dense()

        # O MTCNN retorna [quantidade, canais, altura, largura].
        if face.ndim == 4 and face.shape[0] == 1:
            face = face.squeeze(0)

        if face.ndim != 3 or face.shape[0] != 3:
            raise ValueError(
                f"Formato inesperado do recorte facial: {tuple(face.shape)}"
            )

        arr = (
            face.permute(1, 2, 0)
            .clamp(0, 255)
            .byte()
            .cpu()
            .numpy()
        )

        if not np.all(np.isfinite(arr)):
            raise ValueError("Recorte facial contém valores inválidos.")

        return Image.fromarray(arr, mode="RGB")
