"""Galeria de protótipos faciais com validação de compatibilidade do modelo."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np


@dataclass
class Match:
    name: Optional[str]
    score: float
    best_name: Optional[str]


def _l2(x: np.ndarray) -> np.ndarray:
    x = np.asarray(x, dtype=np.float64)

    if not np.all(np.isfinite(x)):
        raise ValueError("Embedding contém valores inválidos.")

    norms = np.linalg.norm(x, axis=-1, keepdims=True)

    if np.any(norms < 1e-12):
        raise ValueError("Embedding possui norma zero.")

    return x / norms


class Gallery:

    def __init__(self, model_id: Optional[str] = None):
        self._sum: Dict[str, np.ndarray] = {}
        self._count: Dict[str, int] = {}
        self.model_id = model_id
        self.embedding_dim: Optional[int] = None

    def names(self) -> List[str]:
        return sorted(self._sum)

    def people(self) -> List[dict]:
        """Retorna os nomes cadastrados e a quantidade de imagens de cada pessoa."""
        return [
            {
                "nome": name,
                "imagens": self._count[name]
            }
            for name in self.names()
        ]

    def __len__(self) -> int:
        return len(self._sum)

    def bind_model(self, model_id: str) -> None:
        if not model_id:
            raise ValueError("Identificador do modelo inválido.")

        if self.model_id and self.model_id != model_id:
            raise ValueError(
                "A galeria foi criada com outro modelo. "
                "Crie uma nova galeria e cadastre novamente as pessoas."
            )

        if self._sum and not self.model_id:
            raise ValueError(
                "Galeria antiga sem identificação do modelo. "
                "Não é seguro reutilizá-la."
            )

        self.model_id = model_id


    def enroll(self, name: str, embeddings: np.ndarray) -> bool:
        name = name.strip()

        if not name:
            raise ValueError("O nome não pode ficar vazio.")

        e = np.atleast_2d(np.asarray(embeddings, dtype=np.float64))

        if e.ndim != 2 or len(e) == 0:
            raise ValueError("Formato de embeddings inválido.")

        if not np.all(np.isfinite(e)):
            raise ValueError("Embeddings contêm valores inválidos.")

        if np.any(np.linalg.norm(e, axis=1) < 1e-12):
            raise ValueError("Existe embedding com norma zero.")

        if self.embedding_dim is not None and e.shape[1] != self.embedding_dim:
            raise ValueError("Dimensão incompatível com a galeria.")

        e = _l2(e)

        if self.embedding_dim is None:
            self.embedding_dim = e.shape[1]

        # Localiza cadastro existente sem diferenciar maiúsculas/minúsculas.
        existing_name = next(
            (n for n in self._sum if n.casefold() == name.casefold()),
            None
        )

        replaced = existing_name is not None

        # Substitui completamente o cadastro anterior.
        if replaced:
            self._sum.pop(existing_name)
            self._count.pop(existing_name)

        # Armazena somente os novos embeddings.
        self._sum[name] = e.sum(axis=0)
        self._count[name] = len(e)

        return replaced


    def remove(self, name: str) -> bool:
        name = name.strip()

        existing_name = next(
            (n for n in self._sum if n.casefold() == name.casefold()),
            None
        )

        if existing_name is None:
            return False

        self._sum.pop(existing_name, None)
        self._count.pop(existing_name, None)

        return True

    def prototypes(self):
        names = self.names()

        if not names:
            dim = self.embedding_dim or 0
            return names, np.zeros((0, dim), dtype=np.float64)

        matrix = np.stack([self._sum[n] for n in names])
        return names, _l2(matrix)

    def identify(self, embedding: np.ndarray, threshold: float) -> Match:
        if not np.isfinite(threshold) or not -1 <= threshold <= 1:
            raise ValueError("Limiar deve estar entre -1 e 1.")

        names, matrix = self.prototypes()

        if not names:
            return Match(None, -1.0, None)

        query = np.asarray(embedding, dtype=np.float64).reshape(-1)

        if self.embedding_dim is not None and query.size != self.embedding_dim:
            raise ValueError("Dimensão do embedding incompatível com a galeria.")

        query = _l2(query)

        scores = matrix @ query
        index = int(np.argmax(scores))
        score = float(scores[index])
        best_name = names[index]

        return Match(
            best_name if score >= threshold else None,
            score,
            best_name
        )

    def save(self, path: str | Path) -> None:
        import os
        import tempfile

        if self.model_id is None:
            raise ValueError("Galeria sem identificacao do modelo.")

        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        names = self.names()

        sums = (
            np.stack([self._sum[n] for n in names])
            if names else np.zeros((0, self.embedding_dim or 0))
        )

        counts = np.array(
            [self._count[n] for n in names],
            dtype=np.int64
        )

        temporary_path = None

        try:
            with tempfile.NamedTemporaryFile(
                mode="wb",
                suffix=".npz",
                prefix=".gallery_",
                dir=path.parent,
                delete=False
            ) as temporary:
                temporary_path = Path(temporary.name)

                np.savez(
                    temporary,
                    names=np.array(names, dtype=str),
                    sums=sums,
                    counts=counts,
                    model_id=np.array(self.model_id),
                    embedding_dim=np.array(self.embedding_dim or 0)
                )

                temporary.flush()
                os.fsync(temporary.fileno())

            os.replace(temporary_path, path)

        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)


    @classmethod
    def load(
        cls,
        path: str | Path,
        expected_model_id: str
    ) -> "Gallery":

        path = Path(path)

        if not path.exists():
            return cls(model_id=expected_model_id)

        with np.load(path, allow_pickle=False) as data:

            if "model_id" not in data.files:
                raise ValueError(
                    "Galeria antiga sem identificação do modelo. "
                    "Crie uma nova galeria."
                )

            stored_model_id = str(data["model_id"].item())

            if stored_model_id != expected_model_id:
                raise ValueError(
                    "Modelo incompatível com a galeria. "
                    "Não misture embeddings de experimentos diferentes."
                )

            gallery = cls(model_id=stored_model_id)

            stored_dim = int(data["embedding_dim"].item())

            if stored_dim < 0:
                raise ValueError("Dimensão inválida na galeria.")

            gallery.embedding_dim = stored_dim or None

            for name, total, count in zip(
                data["names"],
                data["sums"],
                data["counts"]
            ):
                name = str(name)
                count = int(count)

                if count <= 0:
                    raise ValueError("Contagem inválida na galeria.")

                if not np.all(np.isfinite(total)):
                    raise ValueError("Galeria contém dados inválidos.")

                gallery._sum[name] = total.astype(np.float64)
                gallery._count[name] = count

        return gallery