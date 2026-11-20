"""Executa comparacao E07 Legacy x Aligned usando manifesto privado."""

from pathlib import Path
import hashlib
import json
import sys
from datetime import datetime, timezone

from PIL import Image
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from facerec.detection import FaceDetector
from facerec.inference import load_run
from audit_alignment_decisions import audit_paired_decisions

from compare_alignment import (
    collect_paired_faces,
    embed_paired_faces,
    evaluate_end_to_end_identification,
    validate_embedding_map,
)

MANIFEST = ROOT / "data/private/face_alignment_eval/manifest_e07_alignment.json"
RESULT = ROOT / "data/private/face_alignment_eval/results_e07_alignment.json"
RUN = ROOT / "runs/e07_facenet_full"
DEVICE = "cpu"


def main():
    if not MANIFEST.is_file():
        raise RuntimeError("Manifesto nao encontrado.")

    audit_path = (
        ROOT / "data/private/face_alignment_eval/"
        "audit_e07_alignment.json"
    )

    if audit_path.exists():
        raise RuntimeError(
            "Auditoria ja existe. Nao sera sobrescrita."
        )

    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))

    if manifest.get("model") != "e07_facenet_full":
        raise RuntimeError("Modelo incorreto no manifesto.")

    known = manifest["known"]
    unknown = manifest["unknown"]

    if len(known) != 20 or len(unknown) != 20:
        raise RuntimeError("Quantidade inesperada de identidades.")

    if len({p["identity"] for p in known + unknown}) != 40:
        raise RuntimeError("Identidades duplicadas.")

    records = []
    labels = []
    enroll_indices = {}
    probe_indices = []

    for person in known + unknown:
        name = person["identity"]
        is_known = person in known

        if is_known and (
            len(person["enroll"]) != 3 or len(person["probe"]) != 2
        ):
            raise RuntimeError(f"Cadastro invalido: {name}")

        if not is_known and (
            person["enroll"] or len(person["probe"]) != 2
        ):
            raise RuntimeError(f"Desconhecido invalido: {name}")

        for role in ("enroll", "probe"):
            for record in person[role]:
                index = len(records)
                records.append(record)
                labels.append(name)

                if role == "enroll":
                    enroll_indices.setdefault(name, []).append(index)
                else:
                    probe_indices.append(index)

    if len(records) != 140 or len(probe_indices) != 80:
        raise RuntimeError("Quantidade inesperada de imagens.")

    print("[1/6] Verificando integridade das imagens...", flush=True)

    images = []
    hashes = set()

    for record in records:
        path = Path(record["path"])
        content = path.read_bytes()
        digest = hashlib.sha256(content).hexdigest()

        if digest != record["sha256"]:
            raise RuntimeError(f"Hash divergente: {path.name}")

        if digest in hashes:
            raise RuntimeError(f"Imagem duplicada: {path.name}")

        hashes.add(digest)

        with Image.open(path) as img:
            images.append(img.convert("RGB").copy())

    print("[2/6] Carregando E07...", flush=True)

    model, meta, transform = load_run(RUN, device=DEVICE)
    threshold = float(meta["id_threshold"])
    dimension = int(meta["model"]["embedding_dim"])

    print("[3/6] Inicializando detectores...", flush=True)

    legacy = FaceDetector(
        image_size=meta["image_size"],
        device=DEVICE,
        alignment="legacy",
    )

    aligned = FaceDetector(
        image_size=meta["image_size"],
        device=DEVICE,
        alignment="aligned",
    )

    print("[4/6] Processando 140 imagens nos dois modos...", flush=True)

    collected = collect_paired_faces(
        legacy, aligned, images
    )

    print("Estatisticas de deteccao:")
    for mode, stats in collected["stats"].items():
        print(mode, {
            key: stats[key]
            for key in ("success", "no_face", "multiple_faces", "errors")
        })

    print("[5/6] Gerando embeddings...", flush=True)

    with torch.inference_mode():
        embedded = embed_paired_faces(
            model,
            transform,
            collected["pairs"],
            device=DEVICE,
            batch_size=8,
        )

    for mode in ("legacy", "aligned"):
        vectors = validate_embedding_map(
            embedded[mode],
            expected_dim=dimension,
        )

        missing = [
            name
            for name, indices in enroll_indices.items()
            if not any(index in vectors for index in indices)
        ]

        if missing:
            raise RuntimeError(
                f"{mode}: identidades sem cadastro valido: "
                + ", ".join(missing)
            )

    print("[6/6] Avaliando identificacao 1:N...", flush=True)

    evaluation = evaluate_end_to_end_identification(
        embedded,
        labels,
        enroll_indices,
        probe_indices,
        threshold,
    )

    output = {
        "experiment": manifest["experiment"],
        "model": meta["name"],
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "device": DEVICE,
        "threshold": threshold,
        "image_count": len(images),
        "known_identities": len(known),
        "unknown_identities": len(unknown),
        "detection": collected["stats"],
        "both_success": collected["both_success"],
        "identification": evaluation,
        "limitations": manifest["limitations"],
    }

    audit = audit_paired_decisions(
        embedded,
        labels,
        enroll_indices,
        probe_indices,
        threshold,
    )

    if audit["total_probes"] != 80:
        raise RuntimeError("Auditoria com quantidade incorreta.")

    for mode in ("legacy", "aligned"):
        audited = {
            "correct_known": 0,
            "false_reject_known": 0,
            "misidentified_known": 0,
            "false_accept_unknown": 0,
            "detection_fail_known": 0,
            "detection_fail_unknown": 0,
        }

        for item in audit["decisions"]:
            decision = item[mode]
            outcome = decision["outcome"]

            if outcome == "correct":
                audited["correct_known"] += 1
            elif outcome == "false_reject":
                audited["false_reject_known"] += 1
                if decision["similarity"] is None:
                    audited["detection_fail_known"] += 1
            elif outcome == "misidentified":
                audited["misidentified_known"] += 1
            elif outcome == "false_accept":
                audited["false_accept_unknown"] += 1
            elif outcome == "detection_failure_unknown":
                audited["detection_fail_unknown"] += 1

        for key, value in audited.items():
            expected = evaluation["modes"][mode][key]
            if value != expected:
                raise RuntimeError(
                    f"Auditoria divergente: {mode}/{key}: "
                    f"{value} != {expected}"
                )

    audit_result = {
        "experiment": manifest["experiment"],
        "model": meta["name"],
        "threshold": threshold,
        "audit": audit,
        "aggregate_metrics": evaluation,
    }

    audit_path = (
        ROOT / "data/private/face_alignment_eval/"
        "audit_e07_alignment.json"
    )

    with audit_path.open("x", encoding="utf-8") as file:
        json.dump(
            audit_result,
            file,
            indent=2,
            ensure_ascii=False,
        )

    print("\n===== AUDITORIA PAREADA =====")
    print("Consultas:", audit["total_probes"])
    print("Decisoes alteradas:", audit["changed_decisions"])
    print("Auditoria salva em:", audit_path)

    print("\n===== RESULTADO EXPERIMENTAL =====")

    for mode, metrics in evaluation["modes"].items():
        print(f"\n{mode.upper()}")
        for key, value in metrics.items():
            print(f"  {key}: {value}")

    print("\nResultado agregado original preservado em:", RESULT)
    print("Experimento concluido.")


if __name__ == "__main__":
    main()
