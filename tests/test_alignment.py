import numpy as np
import pytest
from PIL import Image

from facerec.alignment import (
    align_face,
    estimate_similarity,
    reference_landmarks,
)


def test_reference_shape():
    points = reference_landmarks(160)
    assert points.shape == (5, 2)
    assert np.isfinite(points).all()


def test_identity_transformation():
    points = reference_landmarks(160)
    matrix = estimate_similarity(points, points)

    np.testing.assert_allclose(matrix, np.eye(3), atol=1e-8)


def test_known_similarity_transformation():
    target = reference_landmarks(160)

    angle = np.deg2rad(12.0)
    rotation = np.array(
        [
            [np.cos(angle), -np.sin(angle)],
            [np.sin(angle), np.cos(angle)],
        ]
    )

    source = (target @ rotation.T) * 1.2 + np.array([15, 20])

    matrix = estimate_similarity(source, target)

    homogeneous = np.column_stack(
        [source, np.ones(len(source))]
    )

    transformed = homogeneous @ matrix

    np.testing.assert_allclose(
        transformed[:, :2],
        target,
        atol=1e-5,
    )


def test_aligned_image_shape():
    image = Image.new("RGB", (240, 240), color="white")
    points = reference_landmarks(160)

    aligned = align_face(image, points, image_size=160)

    assert aligned.size == (160, 160)
    assert aligned.mode == "RGB"


def test_invalid_landmarks():
    image = Image.new("RGB", (240, 240))

    with pytest.raises(ValueError):
        align_face(image, np.zeros((4, 2)))


def test_nan_landmarks():
    image = Image.new("RGB", (240, 240))
    points = reference_landmarks(160)
    points[0, 0] = np.nan

    with pytest.raises(ValueError):
        align_face(image, points)


def test_degenerate_landmarks():
    image = Image.new("RGB", (240, 240))

    with pytest.raises(ValueError):
        align_face(image, np.ones((5, 2)))
