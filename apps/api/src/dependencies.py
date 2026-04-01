"""Shared dependency injection for the operator console API."""

from fastapi import Request

from .services.app_state import AppState


def get_app_state(request: Request) -> AppState:
    """Inject the singleton AppState into route handlers."""
    state: AppState = request.app.state.app_state
    return state
