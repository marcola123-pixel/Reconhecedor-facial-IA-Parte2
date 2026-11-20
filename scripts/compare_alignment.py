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
