import ast
from pathlib import Path

import pytest


SOURCE = Path(__file__).resolve().parents[1] / "app" / "main.py"


def load_config_code():
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))

    selected = []

    for node in tree.body:
        if isinstance(node, ast.Assign):
            names = [
                target.id
                for target in node.targets
                if isinstance(target, ast.Name)
            ]
            if "GALLERY_PATH" in names or "ALIGNMENT" in names:
                selected.append(node)

        elif isinstance(node, ast.If):
            text = ast.unparse(node.test)
            if "ALIGNMENT" in text:
                selected.append(node)

    module = ast.fix_missing_locations(
        ast.Module(body=selected, type_ignores=[])
    )

    return compile(module, str(SOURCE), "exec")


@pytest.mark.parametrize(
    "mode,expected",
    [
        (None, "legacy"),
        ("legacy", "legacy"),
        ("aligned", "aligned"),
        ("ALIGNED", "aligned"),
    ],
)
def test_alignment_modes(monkeypatch, tmp_path, mode, expected):
    import os

    if mode is None:
        monkeypatch.delenv("FACEREC_ALIGNMENT", raising=False)
    else:
        monkeypatch.setenv("FACEREC_ALIGNMENT", mode)

    gallery_path = (
        tmp_path
        / "embeddings"
        / "experiments"
        / "face_alignment"
        / "gallery_experimental.npz"
    )

    monkeypatch.setenv(
        "FACEREC_GALLERY",
        str(gallery_path),
    )

    namespace = {
        "os": os,
        "Path": Path,
        "ROOT": tmp_path,
        "MODEL_ID": "modelo_teste",
    }
    exec(load_config_code(), namespace)

    assert namespace["ALIGNMENT"] == expected

    if expected == "aligned":
        assert namespace["MODEL_ID"] == (
            "modelo_teste:preprocess=aligned-v1"
        )
    else:
        assert namespace["MODEL_ID"] == "modelo_teste"


def test_invalid_alignment(monkeypatch, tmp_path):
    import os

    monkeypatch.setenv("FACEREC_ALIGNMENT", "invalid")
    monkeypatch.setenv(
        "FACEREC_GALLERY",
        str(tmp_path / "gallery_experimental.npz"),
    )

    with pytest.raises(ValueError):
        exec(load_config_code(), {"os": os, "Path": Path, "ROOT": tmp_path})


def test_aligned_requires_explicit_gallery(monkeypatch, tmp_path):
    import os

    monkeypatch.setenv("FACEREC_ALIGNMENT", "aligned")
    monkeypatch.delenv("FACEREC_GALLERY", raising=False)

    with pytest.raises(ValueError):
        exec(load_config_code(), {"os": os, "Path": Path, "ROOT": tmp_path})


def test_aligned_rejects_default_gallery(monkeypatch, tmp_path):
    import os

    monkeypatch.setenv("FACEREC_ALIGNMENT", "aligned")
    monkeypatch.setenv(
        "FACEREC_GALLERY",
        "embeddings/gallery.npz",
    )

    with pytest.raises(ValueError):
        exec(load_config_code(), {"os": os, "Path": Path, "ROOT": tmp_path})


@pytest.mark.parametrize(
    "relative_path",
    [
        "embeddings/gallery_entrega_teste.npz",
        "embeddings/gallery.npz",
        "embeddings/experiments/outside.npz",
        "embeddings/experiments/face_alignment/../outside.npz",
        "embeddings/experiments/face_alignment/../../gallery.npz",
        "embeddings/experiments/face_alignment/gallery.txt",
    ],
)
def test_aligned_rejects_unsafe_gallery_paths(
    monkeypatch, tmp_path, relative_path
):
    import os

    monkeypatch.setenv("FACEREC_ALIGNMENT", "aligned")
    monkeypatch.setenv("FACEREC_GALLERY", relative_path)

    namespace = {
        "os": os,
        "Path": Path,
        "ROOT": tmp_path,
        "MODEL_ID": "modelo_teste",
    }

    with pytest.raises(ValueError):
        exec(load_config_code(), namespace)


def test_aligned_accepts_experimental_gallery(monkeypatch, tmp_path):
    import os

    monkeypatch.setenv("FACEREC_ALIGNMENT", "aligned")
    monkeypatch.setenv(
        "FACEREC_GALLERY",
        "embeddings/experiments/face_alignment/gallery_aligned_v1.npz",
    )

    namespace = {
        "os": os,
        "Path": Path,
        "ROOT": tmp_path,
        "MODEL_ID": "modelo_teste",
    }

    exec(load_config_code(), namespace)

    assert namespace["ALIGNMENT"] == "aligned"
    assert namespace["MODEL_ID"] == (
        "modelo_teste:preprocess=aligned-v1"
    )



def test_aligned_normalizes_relative_gallery_path(
    monkeypatch, tmp_path
):
    import os

    relative_path = (
        "embeddings/experiments/"
        "face_alignment/gallery_aligned_v1.npz"
    )

    monkeypatch.setenv("FACEREC_ALIGNMENT", "aligned")
    monkeypatch.setenv("FACEREC_GALLERY", relative_path)

    namespace = {
        "os": os,
        "Path": Path,
        "ROOT": tmp_path,
        "MODEL_ID": "modelo_teste",
    }

    exec(load_config_code(), namespace)

    expected_path = (tmp_path / relative_path).resolve()

    assert namespace["GALLERY_PATH"] == str(expected_path)
