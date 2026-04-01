"""Phase 6 tests — EnvironmentGuard (6+ tests)."""

from __future__ import annotations

import os

import pytest

from packages.contracts.enums import Mode
from packages.utils.env_guard import EnvironmentGuard


@pytest.fixture
def guard() -> EnvironmentGuard:
    return EnvironmentGuard()


class TestEnvironmentGuard:
    def test_assert_paper_mode_passes_in_paper(self, guard: EnvironmentGuard) -> None:
        os.environ["MODE"] = "paper"
        try:
            guard.assert_paper_mode()  # Should not raise
        finally:
            os.environ.pop("MODE", None)

    def test_assert_paper_mode_raises_in_shadow_live(
        self, guard: EnvironmentGuard
    ) -> None:
        os.environ["MODE"] = "shadow-live"
        try:
            with pytest.raises(OSError, match="paper mode"):
                guard.assert_paper_mode()
        finally:
            os.environ.pop("MODE", None)

    def test_assert_not_live_passes_in_paper(self, guard: EnvironmentGuard) -> None:
        os.environ["MODE"] = "paper"
        os.environ["ARMED_LIVE"] = "false"
        try:
            guard.assert_not_live()  # Should not raise
        finally:
            os.environ.pop("MODE", None)
            os.environ.pop("ARMED_LIVE", None)

    def test_assert_not_live_passes_in_shadow_live(
        self, guard: EnvironmentGuard
    ) -> None:
        os.environ["MODE"] = "shadow-live"
        os.environ["ARMED_LIVE"] = "false"
        try:
            guard.assert_not_live()  # Should not raise
        finally:
            os.environ.pop("MODE", None)
            os.environ.pop("ARMED_LIVE", None)

    def test_assert_not_live_raises_in_live_armed(
        self, guard: EnvironmentGuard
    ) -> None:
        os.environ["MODE"] = "live"
        os.environ["ARMED_LIVE"] = "true"
        try:
            with pytest.raises(OSError, match="ARMED_LIVE=true"):
                guard.assert_not_live()
        finally:
            os.environ.pop("MODE", None)
            os.environ.pop("ARMED_LIVE", None)

    def test_assert_not_live_passes_in_live_unarmed(
        self, guard: EnvironmentGuard
    ) -> None:
        os.environ["MODE"] = "live"
        os.environ["ARMED_LIVE"] = "false"
        try:
            guard.assert_not_live()  # Should not raise
        finally:
            os.environ.pop("MODE", None)
            os.environ.pop("ARMED_LIVE", None)

    def test_is_armed_live_reads_env(self, guard: EnvironmentGuard) -> None:
        os.environ["ARMED_LIVE"] = "true"
        try:
            assert guard.is_armed_live() is True
        finally:
            os.environ.pop("ARMED_LIVE", None)

    def test_is_armed_live_defaults_false(self, guard: EnvironmentGuard) -> None:
        os.environ.pop("ARMED_LIVE", None)
        assert guard.is_armed_live() is False

    def test_get_mode_reads_env(self, guard: EnvironmentGuard) -> None:
        os.environ["MODE"] = "shadow-live"
        try:
            assert guard.get_mode() == Mode.SHADOW_LIVE
        finally:
            os.environ.pop("MODE", None)
