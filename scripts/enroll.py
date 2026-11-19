"""Cadastro e remoção de pessoas sem retreinar o modelo."""

import argparse
import sys

from pathlib import Path

sys.path.insert(
    0,
    str(Path(__file__).resolve().parents[1] / "src")
)

import torch

from PIL import Image

from facerec.detection import FaceDetector
from facerec.gallery import Gallery
from facerec.inference import (
    embed_images,
    load_run,
    run_fingerprint
)
from facerec.splits import IMG_EXT


def main():

    parser = argparse.ArgumentParser()

    parser.add_argument("--run", required=True)
    parser.add_argument("--name")
    parser.add_argument("--images")
    parser.add_argument("--remove")
    parser.add_argument(
        "--gallery",
        default="embeddings/gallery.npz"
    )

    args = parser.parse_args()

    model_id = run_fingerprint(args.run)

    gallery = Gallery.load(
        args.gallery,
        expected_model_id=model_id
    )

    # Remoção de pessoa
    if args.remove:

        removed = gallery.remove(args.remove)

        if removed:
            gallery.save(args.gallery)
            print("Pessoa removida com sucesso.")
        else:
            print("Pessoa não encontrada.")

        return

    if not args.name or not args.images:
        parser.error(
            "Informe --name e --images ou utilize --remove."
        )

    image_dir = Path(args.images)

    if not image_dir.exists() or not image_dir.is_dir():
        sys.exit("A pasta de imagens não existe.")

    image_files = sorted(
        f for f in image_dir.iterdir()
        if f.is_file() and f.suffix.lower() in IMG_EXT
    )

    if len(image_files) < 3:
        sys.exit("Informe pelo menos 3 imagens.")

    device = "cuda" if torch.cuda.is_available() else "cpu"

    model, meta, transform = load_run(args.run, device)

    detector = FaceDetector(
        image_size=meta["image_size"],
        device=device
    )

    faces = []

    for file_path in image_files:

        try:
            with Image.open(file_path) as image:
                image = image.convert("RGB")
                face = detector.crop(image)

            if face is not None:
                faces.append(face)

        except Exception as error:
            print(f"Imagem ignorada: {file_path.name} ({error})")

    if len(faces) < 3:
        sys.exit(
            f"Somente {len(faces)} rosto(s) válido(s) encontrado(s). "
            "São necessários pelo menos 3."
        )

    embeddings = embed_images(
        model,
        transform,
        faces,
        device
    )

    gallery.enroll(args.name, embeddings)
    gallery.save(args.gallery)

    print("\nCadastro concluído!")
    print(f"Fotos válidas: {len(faces)}")
    print(f"Pessoas na galeria: {len(gallery)}")
    print(f"Modelo utilizado: {model_id[:16]}...")


if __name__ == "__main__":
    main()