"""Comparador experimental de pre-processamento facial.

Nao altera galerias, pesos ou imagens originais.
"""

from __future__ import annotations

from time import perf_counter

from PIL import Image


def evaluate_detector(detector, images):
    """Avalia um detector sobre uma sequencia de imagens PIL."""

    results = {
        "total": 0,
        "success": 0,
        "no_face": 0,
        "multiple_faces": 0,
        "errors": 0,
        "total_seconds": 0.0,
    }

    from facerec.detection import MultipleFacesError

    for image in images:
        results["total"] += 1

        start = perf_counter()

        try:
            face = detector.crop(image)

            if face is None:
                results["no_face"] += 1
            else:
                results["success"] += 1

        except MultipleFacesError:
            results["multiple_faces"] += 1

        except Exception:
            results["errors"] += 1

        finally:
            results["total_seconds"] += perf_counter() - start

    total = results["total"]

    results["success_rate"] = (
        results["success"] / total if total else None
    )

    results["mean_seconds"] = (
        results["total_seconds"] / total if total else None
    )

    return results


def compare_detectors(legacy_detector, aligned_detector, images):
    """Compara detectores utilizando as mesmas imagens."""

    images = list(images)

    return {
        "legacy": evaluate_detector(legacy_detector, images),
        "aligned": evaluate_detector(aligned_detector, images),
    }



def collect_paired_faces(legacy_detector, aligned_detector, images):
    """Coleta recortes pareados, alternando a ordem dos detectores.

    Retorna recortes em memoria e estatisticas agregadas.
    Nao salva imagens nem embeddings.
    """
    from facerec.detection import MultipleFacesError

    detectors = {
        "legacy": legacy_detector,
        "aligned": aligned_detector,
    }

    stats = {
        mode: {
            "total": 0,
            "success": 0,
            "no_face": 0,
            "multiple_faces": 0,
            "errors": 0,
            "total_seconds": 0.0,
        }
        for mode in detectors
    }

    pairs = []

    for index, image in enumerate(images):
        order = (
            ("legacy", "aligned")
            if index % 2 == 0
            else ("aligned", "legacy")
        )

        faces = {"legacy": None, "aligned": None}
        outcomes = {}

        for mode in order:
            result = stats[mode]
            result["total"] += 1

            start = perf_counter()

            try:
                face = detectors[mode].crop(image)

                if face is None:
                    outcome = "no_face"
                else:
                    outcome = "success"
                    faces[mode] = face

            except MultipleFacesError:
                outcome = "multiple_faces"

            except Exception:
                outcome = "errors"

            finally:
                result["total_seconds"] += perf_counter() - start

            result[outcome] += 1
            outcomes[mode] = outcome

        pairs.append({
            "faces": faces,
            "outcomes": outcomes,
        })

    for result in stats.values():
        total = result["total"]

        result["success_rate"] = (
            result["success"] / total if total else None
        )
        result["mean_seconds"] = (
            result["total_seconds"] / total if total else None
        )

    return {
        "stats": stats,
        "pairs": pairs,
        "both_success": sum(
            pair["outcomes"]["legacy"] == "success"
            and pair["outcomes"]["aligned"] == "success"
            for pair in pairs
        ),
    }



def embed_paired_faces(
    model,
    transform,
    pairs,
    device="cpu",
    batch_size=16,
):
    """Gera embeddings dos recortes pareados sem persistencia.

    Mantem indices originais para permitir comparacao justa.
    Normaliza explicitamente os embeddings em L2.
    """
    import numpy as np
    from facerec.inference import embed_images

    if batch_size < 1:
        raise ValueError("batch_size deve ser positivo.")

    output = {}

    for mode in ("legacy", "aligned"):
        indices = []
        vectors = []

        valid = [
            (index, pair["faces"][mode])
            for index, pair in enumerate(pairs)
            if pair["outcomes"][mode] == "success"
            and pair["faces"][mode] is not None
        ]

        for start in range(0, len(valid), batch_size):
            batch = valid[start:start + batch_size]

            images = [face for _, face in batch]

            embeddings = np.asarray(
                embed_images(
                    model,
                    transform,
                    images,
                    device=device,
                ),
                dtype=np.float64,
            )

            if embeddings.ndim != 2:
                raise ValueError("Embeddings devem ser 2D.")

            if embeddings.shape[0] != len(batch):
                raise ValueError("Quantidade de embeddings incorreta.")

            if not np.all(np.isfinite(embeddings)):
                raise ValueError("Embeddings nao finitos.")

            norms = np.linalg.norm(
                embeddings,
                axis=1,
                keepdims=True,
            )

            if np.any(norms <= 1e-12):
                raise ValueError("Embedding com norma zero.")

            embeddings = embeddings / norms

            indices.extend(index for index, _ in batch)
            vectors.extend(embeddings)

        output[mode] = {
            "indices": np.asarray(indices, dtype=np.int64),
            "embeddings": (
                np.stack(vectors)
                if vectors
                else np.empty((0, 0), dtype=np.float64)
            ),
        }

    return output



def evaluate_paired_identification(
    embedded,
    labels,
    enroll_indices,
    probe_indices,
    threshold,
):
    """Compara identificacao 1:N sobre indices validos nos dois modos.

    enroll_indices: dict {identidade: [indices de cadastro]}
    probe_indices: indices de teste, sem sobreposicao com cadastro
    labels: identidade original de cada imagem
    """
    import numpy as np
    from facerec.metrics import open_set_identification

    labels = np.asarray(labels)
    threshold = float(threshold)

    if not np.isfinite(threshold):
        raise ValueError("Threshold deve ser finito.")

    if not enroll_indices:
        raise ValueError("Nenhuma identidade cadastrada.")

    enroll = {
        name: [int(i) for i in indices]
        for name, indices in enroll_indices.items()
    }
    probes = [int(i) for i in probe_indices]

    all_enroll = [i for indices in enroll.values() for i in indices]

    if not all_enroll or any(not indices for indices in enroll.values()):
        raise ValueError("Cada identidade precisa de imagens de cadastro.")

    if len(all_enroll) != len(set(all_enroll)):
        raise ValueError("Indices de cadastro duplicados.")

    if len(probes) != len(set(probes)):
        raise ValueError("Indices de teste duplicados.")

    if set(all_enroll) & set(probes):
        raise ValueError("Cadastro e teste nao podem compartilhar imagens.")

    selected = set(all_enroll) | set(probes)

    if any(i < 0 or i >= len(labels) for i in selected):
        raise ValueError("Indice fora do dataset.")

    for name, indices in enroll.items():
        if any(labels[i] != name for i in indices):
            raise ValueError("Identidade de cadastro inconsistente.")

    maps = {}

    for mode in ("legacy", "aligned"):
        indices = np.asarray(embedded[mode]["indices"], dtype=np.int64)
        vectors = np.asarray(embedded[mode]["embeddings"])

        if len(indices) != len(vectors):
            raise ValueError("Indices e embeddings inconsistentes.")

        if len(set(indices.tolist())) != len(indices):
            raise ValueError("Indices de embeddings duplicados.")

        maps[mode] = dict(zip(indices.tolist(), vectors))

    common = set(maps["legacy"]) & set(maps["aligned"])

    if not set(all_enroll).issubset(common):
        raise ValueError(
            "Nem todas as imagens de cadastro possuem embeddings pareados."
        )

    common_probes = [i for i in probes if i in common]

    if not common_probes:
        raise ValueError("Nenhuma imagem de teste valida nos dois modos.")

    known_names = set(enroll)

    probe_labels = labels[common_probes]
    probe_known = np.asarray(
        [label in known_names for label in probe_labels],
        dtype=bool,
    )

    if not probe_known.any() or probe_known.all():
        raise ValueError(
            "Avaliacao exige probes conhecidos e desconhecidos."
        )

    result = {
        "threshold": threshold,
        "n_common_probes": len(common_probes),
        "n_excluded_probes": len(probes) - len(common_probes),
        "modes": {},
    }

    for mode in ("legacy", "aligned"):
        vectors = maps[mode]
        names = sorted(enroll)

        prototypes = []

        for name in names:
            prototype = np.mean(
                [vectors[i] for i in enroll[name]],
                axis=0,
            )

            norm = np.linalg.norm(prototype)

            if not np.isfinite(norm) or norm <= 1e-12:
                raise ValueError("Prototipo invalido.")

            prototypes.append(prototype / norm)

        proto_matrix = np.stack(prototypes)

        probe_matrix = np.stack(
            [vectors[i] for i in common_probes]
        )

        result["modes"][mode] = open_set_identification(
            probe_matrix,
            probe_labels,
            probe_known,
            proto_matrix,
            names,
            threshold,
        )

    return result
