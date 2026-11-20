"""Testes do comparador experimental de alinhamento."""

import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from compare_alignment import (compare_detectors, evaluate_detector, collect_paired_faces, embed_paired_faces)
from facerec.detection import MultipleFacesError


class FakeDetector:
    def __init__(self, behavior):
        self.behavior = behavior
        self.calls = []

    def crop(self, image):
        self.calls.append(image)
        result = self.behavior

        if isinstance(result, Exception):
            raise result

        return result


def test_successful_detection():
    image = Image.new("RGB", (32, 32))
    detector = FakeDetector(image)

    result = evaluate_detector(detector, [image])

    assert result["total"] == 1
    assert result["success"] == 1
    assert result["success_rate"] == 1.0


def test_no_face():
    detector = FakeDetector(None)

    result = evaluate_detector(
        detector, [Image.new("RGB", (32, 32))]
    )

    assert result["no_face"] == 1
    assert result["success"] == 0


def test_multiple_faces():
    detector = FakeDetector(
        MultipleFacesError("Multiplos rostos")
    )

    result = evaluate_detector(
        detector, [Image.new("RGB", (32, 32))]
    )

    assert result["multiple_faces"] == 1
    assert result["errors"] == 0


def test_unexpected_error():
    detector = FakeDetector(ValueError("Falha simulada"))

    result = evaluate_detector(
        detector, [Image.new("RGB", (32, 32))]
    )

    assert result["errors"] == 1
    assert result["success"] == 0


def test_empty_dataset():
    detector = FakeDetector(None)

    result = evaluate_detector(detector, [])

    assert result["total"] == 0
    assert result["success_rate"] is None
    assert result["mean_seconds"] is None


def test_both_modes_receive_same_images():
    images = [
        Image.new("RGB", (32, 32)),
        Image.new("RGB", (48, 48)),
    ]

    legacy = FakeDetector(images[0])
    aligned = FakeDetector(images[0])

    result = compare_detectors(legacy, aligned, images)

    assert legacy.calls == images
    assert aligned.calls == images
    assert result["legacy"]["total"] == 2
    assert result["aligned"]["total"] == 2


def test_total_matches_all_outcomes():
    image = Image.new("RGB", (32, 32))
    detector = FakeDetector(None)

    result = evaluate_detector(detector, [image, image])

    assert result["total"] == (
        result["success"]
        + result["no_face"]
        + result["multiple_faces"]
        + result["errors"]
    )



def test_paired_collection_alternates_order():
    calls = []

    class OrderedDetector:
        def __init__(self, mode):
            self.mode = mode

        def crop(self, image):
            calls.append(self.mode)
            return image

    images = [Image.new("RGB", (32, 32)) for _ in range(3)]

    result = collect_paired_faces(
        OrderedDetector("legacy"),
        OrderedDetector("aligned"),
        images,
    )

    assert calls == [
        "legacy", "aligned",
        "aligned", "legacy",
        "legacy", "aligned",
    ]
    assert result["both_success"] == 3


def test_paired_collection_handles_different_outcomes():
    image = Image.new("RGB", (32, 32))

    result = collect_paired_faces(
        FakeDetector(image),
        FakeDetector(None),
        [image],
    )

    assert result["stats"]["legacy"]["success"] == 1
    assert result["stats"]["aligned"]["no_face"] == 1
    assert result["both_success"] == 0
    assert result["pairs"][0]["faces"]["aligned"] is None


def test_paired_collection_empty_input():
    result = collect_paired_faces(
        FakeDetector(None),
        FakeDetector(None),
        [],
    )

    assert result["pairs"] == []
    assert result["both_success"] == 0
    assert result["stats"]["legacy"]["success_rate"] is None
    assert result["stats"]["aligned"]["mean_seconds"] is None



def test_embed_paired_faces_preserves_indices(monkeypatch):
    import numpy as np
    import facerec.inference as inference

    def fake_embed(model, transform, images, device="cpu"):
        return np.tile(
            np.array([[3.0, 4.0]]),
            (len(images), 1),
        )

    monkeypatch.setattr(inference, "embed_images", fake_embed)

    image = Image.new("RGB", (32, 32))

    pairs = [
        {
            "faces": {"legacy": image, "aligned": image},
            "outcomes": {"legacy": "success", "aligned": "success"},
        },
        {
            "faces": {"legacy": None, "aligned": image},
            "outcomes": {"legacy": "no_face", "aligned": "success"},
        },
    ]

    result = embed_paired_faces(
        object(), None, pairs, batch_size=1
    )

    assert result["legacy"]["indices"].tolist() == [0]
    assert result["aligned"]["indices"].tolist() == [0, 1]

    np.testing.assert_allclose(
        np.linalg.norm(result["legacy"]["embeddings"], axis=1),
        [1.0],
    )

    np.testing.assert_allclose(
        np.linalg.norm(result["aligned"]["embeddings"], axis=1),
        [1.0, 1.0],
    )


def test_embed_paired_faces_empty(monkeypatch):
    result = embed_paired_faces(object(), None, [])

    assert result["legacy"]["indices"].size == 0
    assert result["aligned"]["indices"].size == 0
    assert result["legacy"]["embeddings"].shape == (0, 0)


def test_embed_paired_faces_rejects_invalid_batch_size():
    import pytest

    with pytest.raises(ValueError):
        embed_paired_faces(
            object(), None, [], batch_size=0
        )
