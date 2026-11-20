"""Testes do comparador experimental de alinhamento."""

import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from compare_alignment import compare_detectors, evaluate_detector
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
