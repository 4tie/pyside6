"""Unit tests for AISettings legacy selected_model migration.

Validates: Requirements 1.6
"""
import pytest

from app.core.models.settings_models import AISettings


def test_legacy_selected_model_only():
    """Dict with selected_model and no chat_model → chat_model equals legacy value, task_model is empty."""
    instance = AISettings.model_validate({"selected_model": "my-model"})
    assert instance.chat_model == "my-model"
    assert instance.task_model == ""


def test_chat_model_takes_precedence_over_selected_model():
    """Dict with both selected_model and chat_model → chat_model wins, selected_model is ignored."""
    instance = AISettings.model_validate({"selected_model": "old", "chat_model": "new"})
    assert instance.chat_model == "new"


def test_neither_selected_model_nor_chat_model():
    """Dict with neither selected_model nor chat_model → chat_model defaults to empty string."""
    instance = AISettings.model_validate({})
    assert instance.chat_model == ""
