import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from audit_alignment_decisions import audit_paired_decisions


def test_audit_detects_changed_decision():
    labels = ["Ana", "Ana", "Desconhecido"]

    enroll_indices = {"Ana": [0]}
    probe_indices = [1, 2]

    embedded = {
        "legacy": {
            "indices": np.array([0, 1, 2]),
            "embeddings": np.array([
                [1.0, 0.0],
                [1.0, 0.0],
                [0.0, 1.0],
            ]),
        },
        "aligned": {
            "indices": np.array([0, 1, 2]),
            "embeddings": np.array([
                [1.0, 0.0],
                [0.0, 1.0],
                [0.0, 1.0],
            ]),
        },
    }

    result = audit_paired_decisions(
        embedded,
        labels,
        enroll_indices,
        probe_indices,
        threshold=0.8,
    )

    assert result["total_probes"] == 2
    assert result["changed_decisions"] == 1

    first = result["decisions"][0]

    assert first["legacy"]["outcome"] == "correct"
    assert first["aligned"]["outcome"] == "false_reject"

    second = result["decisions"][1]

    assert second["legacy"]["outcome"] == "correct_reject"
    assert second["aligned"]["outcome"] == "correct_reject"
