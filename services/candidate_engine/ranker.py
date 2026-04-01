"""Candidate ranker — ranks and limits swing candidates per charter §6.6 R5."""

from __future__ import annotations

from packages.contracts.candidates import SwingCandidate


def rank_swing_candidates(
    candidates: list[SwingCandidate],
    max_entries: int = 2,
) -> list[SwingCandidate]:
    """
    Rank passing swing candidates and return top `max_entries`.

    Ranking criteria (priority order):
    1. Volume ratio (higher is better — stronger conviction)
    2. Risk-reward potential (lower ATR/price ratio = tighter risk)
    3. Alphabetical by symbol (tiebreaker for determinism)

    Only candidates with passes_all_entry_conditions=True are ranked.
    """
    passing = [c for c in candidates if c.passes_all_entry_conditions]

    def sort_key(c: SwingCandidate) -> tuple[float, float, str]:
        # Negative volume_ratio for descending sort
        vol = -float(c.volume_ratio)
        # ATR relative to price — lower is tighter risk, better
        atr_ratio = float(c.atr_14) / float(c.close) if float(c.close) > 0 else 999.0
        return (vol, atr_ratio, c.symbol)

    ranked = sorted(passing, key=sort_key)
    return ranked[:max_entries]
