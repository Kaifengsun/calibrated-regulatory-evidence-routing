"""Leakage-safe grouped folds fixed by source-group hashing."""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from dataclasses import dataclass

from evidence_routing.schemas import QueryRecord, SplitAssignment


@dataclass(frozen=True)
class FoldPartitions:
    outer_test_fold: int
    calibration_fold: int
    train_question_ids: tuple[str, ...]
    calibration_question_ids: tuple[str, ...]
    test_question_ids: tuple[str, ...]


def assign_grouped_folds(
    queries: Sequence[QueryRecord], seed: int = 20260723, folds: int = 5
) -> list[SplitAssignment]:
    """Assign each document/standard group to one stable fold."""
    if folds != 5:
        raise ValueError("the frozen Pilot uses exactly five folds")
    assignments = []
    for query in queries:
        digest = hashlib.sha256(f"{seed}:{query.source_group_id}".encode()).hexdigest()
        assignments.append(
            SplitAssignment(
                question_id=query.question_id,
                source_group_id=query.source_group_id,
                domain=query.domain,
                fold=int(digest, 16) % folds,
                assignment_seed=seed,
                assignment_hash=digest,
            )
        )
    groups = {}
    for row in assignments:
        prior = groups.setdefault(row.source_group_id, row.fold)
        if prior != row.fold:
            raise AssertionError("source group crosses folds")
    return sorted(assignments, key=lambda row: row.question_id)


def make_fold_partitions(
    assignments: Sequence[SplitAssignment], outer_test_fold: int
) -> FoldPartitions:
    """Apply the frozen test=i, calibration=(i+1) mod 5 rotation."""
    if not 0 <= outer_test_fold < 5:
        raise ValueError("outer_test_fold must be between zero and four")
    calibration_fold = (outer_test_fold + 1) % 5
    train = tuple(
        sorted(
            row.question_id
            for row in assignments
            if row.fold not in {outer_test_fold, calibration_fold}
        )
    )
    calibration = tuple(
        sorted(row.question_id for row in assignments if row.fold == calibration_fold)
    )
    test = tuple(sorted(row.question_id for row in assignments if row.fold == outer_test_fold))
    if not train or not calibration or not test:
        raise ValueError("each partition must contain at least one question")
    if set(train) & set(calibration) or set(train) & set(test) or set(calibration) & set(test):
        raise AssertionError("question identity crosses partitions")
    group_by_question = {row.question_id: row.source_group_id for row in assignments}
    group_sets = [
        set(group_by_question[item] for item in partition)
        for partition in (train, calibration, test)
    ]
    if (
        group_sets[0] & group_sets[1]
        or group_sets[0] & group_sets[2]
        or group_sets[1] & group_sets[2]
    ):
        raise AssertionError("source group crosses partitions")
    return FoldPartitions(outer_test_fold, calibration_fold, train, calibration, test)
