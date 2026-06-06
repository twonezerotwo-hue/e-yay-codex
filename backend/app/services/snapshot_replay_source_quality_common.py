from __future__ import annotations

from app.services.snapshot_replay_source_common import CRITICAL_SEVERITY_MIN_RANK, SEVERITY_LABEL_SCORES, WARNING_SEVERITY_MAX_RANK, WARNING_SEVERITY_MIN_RANK


def derive_severity_label_from_rank(severity_rank: int) -> str:
    if severity_rank >= CRITICAL_SEVERITY_MIN_RANK:
        return "critical"
    if WARNING_SEVERITY_MIN_RANK <= severity_rank <= WARNING_SEVERITY_MAX_RANK:
        return "warning"
    return "info"


def severity_label_score(severity_level: str) -> int:
    return SEVERITY_LABEL_SCORES.get(severity_level, 0)


def severity_rank_density(
    severity_rank_total: int,
    severity_ranking_feature_count: int,
) -> float:
    if severity_ranking_feature_count <= 0:
        return 0.0
    return round(severity_rank_total / severity_ranking_feature_count, 2)


def severity_rank_spread(severity_ranks: tuple[int, ...]) -> int:
    if not severity_ranks:
        return 0
    return max(severity_ranks) - min(severity_ranks)


def severity_ranking_order_key(
    *,
    severity_rank: int,
    feature_name: str,
    status: str,
    severity_level: str,
) -> tuple[int, str, str, str]:
    return (-severity_rank, feature_name, status, severity_level)


def severity_ranking_gap_sequence(
    entries: tuple[tuple[str, int, str, str], ...],
) -> tuple[int, ...]:
    return tuple(
        entries[index][1] - entries[index + 1][1]
        for index in range(len(entries) - 1)
    )


def severity_ranking_gap_magnitude_sequence(
    entries: tuple[tuple[str, int, str, str], ...],
) -> tuple[int, ...]:
    return tuple(
        abs(entries[index][1] - entries[index + 1][1])
        for index in range(len(entries) - 1)
    )

__all__ = [name for name in globals() if not name.startswith('_')]
