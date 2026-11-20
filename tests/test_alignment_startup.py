import importlib
import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

import facerec.detection as detection
import facerec.inference as inference
from facerec.gallery import Gallery


@pytest.mark.parametrize(
    "mode,expected_alignment,expected_id",
    [
        ("legacy", "legacy", "modelo_teste"),
        (
            "aligned",
            "aligned",
            "modelo_teste:preprocess=aligned-v1",
        ),
    ],
)
def test_api_startup_alignment(
    monkeypatch,
    tmp_path,
    mode,
    expected_alignment,
    expected_id,
):
    project_root = Path(__file__).resolve().parents[1]

    if mode == "aligned":
        gallery_path = (
            project_root
            / "embeddings"
            / "experiments"
            / "face_alignment"
            / "gallery_aligned_startup_test.npz"
        )
    else:
        gallery_path = tmp_path / "gallery_legacy_test.npz"

    # O teste nao deve carregar nem sobrescrever galerias.
    assert not gallery_path.exists(), (
        "Arquivo de teste ja existe. Interrompendo por seguranca."
    )

    captured = {}

    class FakeDetector:
        def __init__(self, image_size, device, alignment):
            captured["alignment"] = alignment

        def crop(self, image):
            return image

    def fake_gallery_load(cls, path, expected_model_id):
        captured["gallery_path"] = str(path)
        captured["expected_model_id"] = expected_model_id
        return Gallery(model_id=expected_model_id)

    fake_meta = {
        "name": "experimento_teste",
        "image_size": 160,
        "id_threshold": 0.5,
    }

    env = {
        "FACEREC_RUN": "modelo_simulado",
        "FACEREC_GALLERY": str(gallery_path),
        "FACEREC_ALIGNMENT": mode,
        "FACEREC_HISTORY_DB": str(tmp_path / "history.db"),
        "FACEREC_SECURITY_AUDIT_DB": str(tmp_path / "audit.db"),
        "FACEREC_RATE_LIMIT_ENABLED": "0",
        "PORTEIRO_TOKEN": "token-de-teste",
    }

    previous_module = sys.modules.get("app.main")

    try:
        with patch.dict(os.environ, env), patch.object(
            inference,
            "load_run",
            return_value=("modelo_falso", fake_meta, "transform_falso"),
        ), patch.object(
            inference,
            "run_fingerprint",
            return_value="modelo_teste",
        ), patch.object(
            detection,
            "FaceDetector",
            FakeDetector,
        ), patch.object(
            Gallery,
            "load",
            classmethod(fake_gallery_load),
        ):
            sys.modules.pop("app.main", None)
            main = importlib.import_module("app.main")

            assert main.ALIGNMENT == expected_alignment
            assert main.MODEL_ID == expected_id
            assert captured["alignment"] == expected_alignment
            assert captured["expected_model_id"] == expected_id
            assert captured["gallery_path"] == str(gallery_path)
            assert main.GALLERY_PATH == str(gallery_path)
            assert main.gallery.model_id == expected_id

    finally:
        sys.modules.pop("app.main", None)
        if previous_module is not None:
            sys.modules["app.main"] = previous_module

    assert not gallery_path.exists()



def test_gallery_rejects_different_alignment_model_id(tmp_path):
    gallery_path = tmp_path / "gallery_test.npz"

    legacy_id = "modelo_teste"
    aligned_id = "modelo_teste:preprocess=aligned-v1"

    legacy_gallery = Gallery(model_id=legacy_id)
    legacy_gallery.save(gallery_path)

    loaded_legacy = Gallery.load(
        gallery_path,
        expected_model_id=legacy_id,
    )

    assert loaded_legacy.model_id == legacy_id

    with pytest.raises(ValueError, match="incompat"):
        Gallery.load(
            gallery_path,
            expected_model_id=aligned_id,
        )

    # A rejeicao nao pode modificar o arquivo original.
    loaded_again = Gallery.load(
        gallery_path,
        expected_model_id=legacy_id,
    )

    assert loaded_again.model_id == legacy_id
