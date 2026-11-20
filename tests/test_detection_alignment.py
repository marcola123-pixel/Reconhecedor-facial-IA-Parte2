import sys
import types
from unittest.mock import Mock

import numpy as np
import pytest
import torch
from PIL import Image

from facerec.alignment import reference_landmarks
from facerec.detection import FaceDetector, MultipleFacesError


@pytest.fixture
def fake_mtcnn(monkeypatch):
    instance = Mock()

    instance.detect.return_value = (
        np.array([[20, 20, 180, 180]], dtype=float),
        np.array([0.99]),
        reference_landmarks(160)[None, :, :],
    )

    instance.extract.return_value = torch.full(
        (1, 3, 160, 160), 128.0
    )

    fake_module = types.ModuleType("facenet_pytorch")
    fake_module.MTCNN = Mock(return_value=instance)

    monkeypatch.setitem(
        sys.modules,
        "facenet_pytorch",
        fake_module,
    )

    return instance


def test_aligned_returns_rgb_160(fake_mtcnn):
    detector = FaceDetector(alignment="aligned")

    image = Image.new("RGB", (200, 200), "white")
    result = detector.crop(image)

    assert result.mode == "RGB"
    assert result.size == (160, 160)

    fake_mtcnn.detect.assert_called_once()
    assert fake_mtcnn.detect.call_args.kwargs == {
        "landmarks": True
    }

    fake_mtcnn.extract.assert_not_called()


def test_legacy_keeps_original_extraction(fake_mtcnn):
    fake_mtcnn.detect.return_value = (
        np.array([[20, 20, 180, 180]], dtype=float),
        np.array([0.99]),
    )

    detector = FaceDetector()
    image = Image.new("RGB", (200, 200), "white")

    result = detector.crop(image)

    assert result.size == (160, 160)
    fake_mtcnn.extract.assert_called_once()


def test_aligned_no_face(fake_mtcnn):
    fake_mtcnn.detect.return_value = (
        None,
        None,
        None,
    )

    detector = FaceDetector(alignment="aligned")

    assert detector.crop(
        Image.new("RGB", (200, 200))
    ) is None


def test_aligned_rejects_multiple_faces(fake_mtcnn):
    fake_mtcnn.detect.return_value = (
        np.array([
            [10, 10, 90, 90],
            [100, 10, 190, 90],
        ]),
        np.array([0.99, 0.98]),
        np.zeros((2, 5, 2)),
    )

    detector = FaceDetector(alignment="aligned")

    with pytest.raises(MultipleFacesError):
        detector.crop(Image.new("RGB", (200, 200)))


def test_aligned_rejects_missing_landmarks(fake_mtcnn):
    fake_mtcnn.detect.return_value = (
        np.array([[20, 20, 180, 180]]),
        np.array([0.99]),
        None,
    )

    detector = FaceDetector(alignment="aligned")

    with pytest.raises(ValueError, match="Landmarks"):
        detector.crop(Image.new("RGB", (200, 200)))


def test_invalid_alignment_mode(fake_mtcnn):
    with pytest.raises(ValueError):
        FaceDetector(alignment="invalid")
