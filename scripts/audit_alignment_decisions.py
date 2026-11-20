"""Auditoria individual de decisoes Legacy x Aligned."""

import numpy as np

from compare_alignment import validate_embedding_map


def audit_paired_decisions(
    embedded,
    labels,
    enroll_indices,
    probe_indices,
    threshold,
):
    labels = np.asarray(labels)
    names = sorted(enroll_indices)
    known_names = set(names)

    decisions = {}

    for mode in ("legacy", "aligned"):
        vectors = validate_embedding_map(embedded[mode])

        prototypes = []

        for name in names:
            available = [
                vectors[index]
                for index in enroll_indices[name]
                if index in vectors
            ]

            if not available:
                raise ValueError(
                    f"{mode}: cadastro ausente para {name}"
                )

            prototype = np.mean(available, axis=0)
            norm = np.linalg.norm(prototype)

            if norm <= 1e-12:
                raise ValueError("Prototipo invalido.")

            prototypes.append(prototype / norm)

        matrix = np.stack(prototypes)

        mode_decisions = {}

        for index in probe_indices:
            expected = str(labels[index])
            is_known = expected in known_names

            if index not in vectors:
                mode_decisions[index] = {
                    "expected": expected,
                    "known": is_known,
                    "predicted": None,
                    "similarity": None,
                    "accepted": False,
                    "outcome": (
                        "false_reject"
                        if is_known
                        else "detection_failure_unknown"
                    ),
                }
                continue

            scores = matrix @ vectors[index]
            best = int(np.argmax(scores))

            similarity = float(scores[best])
            accepted = similarity >= threshold
            predicted = names[best] if accepted else None

            if is_known:
                if not accepted:
                    outcome = "false_reject"
                elif predicted == expected:
                    outcome = "correct"
                else:
                    outcome = "misidentified"
            else:
                outcome = (
                    "false_accept"
                    if accepted
                    else "correct_reject"
                )

            mode_decisions[index] = {
                "expected": expected,
                "known": is_known,
                "predicted": predicted,
                "similarity": similarity,
                "accepted": accepted,
                "outcome": outcome,
            }

        decisions[mode] = mode_decisions

    comparison = []

    for index in probe_indices:
        legacy = decisions["legacy"][index]
        aligned = decisions["aligned"][index]

        comparison.append({
            "index": int(index),
            "expected": legacy["expected"],
            "known": legacy["known"],
            "legacy": legacy,
            "aligned": aligned,
            "decision_changed": (
                legacy["predicted"] != aligned["predicted"]
                or legacy["outcome"] != aligned["outcome"]
            ),
        })

    return {
        "total_probes": len(comparison),
        "changed_decisions": sum(
            item["decision_changed"]
            for item in comparison
        ),
        "decisions": comparison,
    }
