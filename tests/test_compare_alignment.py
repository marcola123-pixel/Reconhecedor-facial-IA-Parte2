"""Testes do comparador experimental de alinhamento."""

import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from compare_alignment import (compare_detectors, evaluate_detector, collect_paired_faces, embed_paired_faces, evaluate_paired_identification)
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



def _synthetic_identification_data():
    import numpy as np

    labels = ["alice", "alice", "bob", "bob", "unknown"]

    vectors = np.array([
        [1.0, 0.0],
        [0.99, 0.10],
        [0.0, 1.0],
        [0.10, 0.99],
        [-1.0, 0.0],
    ])

    vectors = vectors / np.linalg.norm(
        vectors, axis=1, keepdims=True
    )

    embedded = {
        mode: {
            "indices": np.arange(5),
            "embeddings": vectors.copy(),
        }
        for mode in ("legacy", "aligned")
    }

    return embedded, labels


def test_paired_identification_success():
    embedded, labels = _synthetic_identification_data()

    result = evaluate_paired_identification(
        embedded,
        labels,
        enroll_indices={"alice": [0], "bob": [2]},
        probe_indices=[1, 3, 4],
        threshold=0.5,
    )

    assert result["n_common_probes"] == 3

    for mode in ("legacy", "aligned"):
        metrics = result["modes"][mode]
        assert metrics["dir"] == 1.0
        assert metrics["far_unknown"] == 0.0


def test_paired_identification_excludes_unpaired_probe():
    embedded, labels = _synthetic_identification_data()

    embedded["aligned"]["indices"] = embedded[
        "aligned"
    ]["indices"][[0, 2, 3, 4]]

    embedded["aligned"]["embeddings"] = embedded[
        "aligned"
    ]["embeddings"][[0, 2, 3, 4]]

    result = evaluate_paired_identification(
        embedded,
        labels,
        enroll_indices={"alice": [0], "bob": [2]},
        probe_indices=[1, 3, 4],
        threshold=0.5,
    )

    assert result["n_common_probes"] == 2
    assert result["n_excluded_probes"] == 1


def test_paired_identification_rejects_data_leakage():
    import pytest

    embedded, labels = _synthetic_identification_data()

    with pytest.raises(ValueError, match="compartilhar"):
        evaluate_paired_identification(
            embedded,
            labels,
            enroll_indices={"alice": [0], "bob": [2]},
            probe_indices=[0, 3, 4],
            threshold=0.5,
        )


def test_paired_identification_requires_unknown_probes():
    import pytest

    embedded, labels = _synthetic_identification_data()

    with pytest.raises(ValueError, match="desconhecidos"):
        evaluate_paired_identification(
            embedded,
            labels,
            enroll_indices={"alice": [0], "bob": [2]},
            probe_indices=[1, 3],
            threshold=0.5,
        )



def test_validate_embedding_map_normalizes():
    import numpy as np
    from compare_alignment import validate_embedding_map

    result = validate_embedding_map({
        "indices": np.array([2, 5]),
        "embeddings": np.array([[3.0, 4.0], [0.0, 2.0]]),
    }, expected_dim=2)

    np.testing.assert_allclose(result[2], [0.6, 0.8])
    np.testing.assert_allclose(result[5], [0.0, 1.0])


def test_validate_embedding_map_rejects_nan():
    import numpy as np
    import pytest
    from compare_alignment import validate_embedding_map

    with pytest.raises(ValueError, match="nao finitos"):
        validate_embedding_map({
            "indices": np.array([0]),
            "embeddings": np.array([[float("nan"), 1.0]]),
        })


def test_validate_embedding_map_rejects_duplicates():
    import numpy as np
    import pytest
    from compare_alignment import validate_embedding_map

    with pytest.raises(ValueError, match="duplicados"):
        validate_embedding_map({
            "indices": np.array([0, 0]),
            "embeddings": np.array([[1.0, 0.0], [0.0, 1.0]]),
        })


def test_validate_embedding_map_rejects_wrong_dimension():
    import numpy as np
    import pytest
    from compare_alignment import validate_embedding_map

    with pytest.raises(ValueError, match="Dimensao"):
        validate_embedding_map({
            "indices": np.array([0]),
            "embeddings": np.array([[1.0, 0.0]]),
        }, expected_dim=512)



def test_identification_rejects_nan_embedding():
    import numpy as np
    import pytest

    embedded, labels = _synthetic_identification_data()

    embedded["aligned"]["embeddings"][1, 0] = np.nan

    with pytest.raises(ValueError, match="nao finitos"):
        evaluate_paired_identification(
            embedded,
            labels,
            enroll_indices={"alice": [0], "bob": [2]},
            probe_indices=[1, 3, 4],
            threshold=0.5,
        )


def test_identification_normalizes_embeddings():
    embedded, labels = _synthetic_identification_data()

    for mode in ("legacy", "aligned"):
        embedded[mode]["embeddings"] *= 5.0

    result = evaluate_paired_identification(
        embedded,
        labels,
        enroll_indices={"alice": [0], "bob": [2]},
        probe_indices=[1, 3, 4],
        threshold=0.5,
    )

    assert result["modes"]["legacy"]["dir"] == 1.0
    assert result["modes"]["aligned"]["dir"] == 1.0


def test_identification_rejects_inconsistent_dimensions():
    import numpy as np
    import pytest

    embedded, labels = _synthetic_identification_data()

    embedded["aligned"]["embeddings"] = np.ones((5, 3))

    with pytest.raises(ValueError, match="Dimensoes"):
        evaluate_paired_identification(
            embedded,
            labels,
            enroll_indices={"alice": [0], "bob": [2]},
            probe_indices=[1, 3, 4],
            threshold=0.5,
        )



def test_end_to_end_counts_missing_known_probe():
    from compare_alignment import evaluate_end_to_end_identification

    embedded, labels = _synthetic_identification_data()

    embedded["aligned"]["indices"] = embedded[
        "aligned"
    ]["indices"][[0, 2, 3, 4]]

    embedded["aligned"]["embeddings"] = embedded[
        "aligned"
    ]["embeddings"][[0, 2, 3, 4]]

    result = evaluate_end_to_end_identification(
        embedded,
        labels,
        enroll_indices={"alice": [0], "bob": [2]},
        probe_indices=[1, 3, 4],
        threshold=0.5,
    )

    assert result["modes"]["legacy"]["dir"] == 1.0
    assert result["modes"]["aligned"]["dir"] == 0.5
    assert result["modes"]["aligned"]["frr_known"] == 0.5
    assert result["modes"]["aligned"]["detection_fail_known"] == 1


def test_end_to_end_counts_missing_unknown_probe():
    from compare_alignment import evaluate_end_to_end_identification

    embedded, labels = _synthetic_identification_data()

    embedded["aligned"]["indices"] = embedded[
        "aligned"
    ]["indices"][:4]

    embedded["aligned"]["embeddings"] = embedded[
        "aligned"
    ]["embeddings"][:4]

    result = evaluate_end_to_end_identification(
        embedded,
        labels,
        enroll_indices={"alice": [0], "bob": [2]},
        probe_indices=[1, 3, 4],
        threshold=0.5,
    )

    assert result["modes"]["aligned"]["far_unknown"] == 0.0
    assert result["modes"]["aligned"]["detection_fail_unknown"] == 1


def test_end_to_end_rejects_missing_enrollment():
    import pytest
    from compare_alignment import evaluate_end_to_end_identification

    embedded, labels = _synthetic_identification_data()

    embedded["aligned"]["indices"] = embedded[
        "aligned"
    ]["indices"][1:]

    embedded["aligned"]["embeddings"] = embedded[
        "aligned"
    ]["embeddings"][1:]

    with pytest.raises(ValueError, match="sem cadastro valido"):
        evaluate_end_to_end_identification(
            embedded,
            labels,
            enroll_indices={"alice": [0], "bob": [2]},
            probe_indices=[1, 3, 4],
            threshold=0.5,
        )


def test_end_to_end_rejects_data_leakage():
    import pytest
    from compare_alignment import evaluate_end_to_end_identification

    embedded, labels = _synthetic_identification_data()

    with pytest.raises(ValueError, match="compartilham"):
        evaluate_end_to_end_identification(
            embedded,
            labels,
            enroll_indices={"alice": [0], "bob": [2]},
            probe_indices=[0, 3, 4],
            threshold=0.5,
        )
