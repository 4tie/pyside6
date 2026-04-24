"""
pattern_database.py — Pattern database loader and storage.

Loads 100 failure patterns from JSON and provides access.
"""
from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from app.core.models.pattern_models import (
    FailurePattern,
    PatternCondition,
    PatternAction,
)
from app.core.parsing.json_parser import parse_json_file, ParseError
from app.core.utils.app_logger import get_logger

_log = get_logger("services.pattern_database")


class PatternDatabase:
    """Database for failure patterns.
    
    Loads patterns from JSON and provides in-memory access.
    """

    _instance = None
    _patterns: List[FailurePattern] = []
    _loaded = False

    def __new__(cls):
        """Singleton pattern to ensure one database instance."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """Initialize the database."""
        pass

    @classmethod
    def load_from_json(cls, json_path: str) -> bool:
        """Load patterns from a JSON file.
        
        Args:
            json_path: Path to the JSON file containing patterns.
            
        Returns:
            True if successful, False otherwise.
        """
        try:
            data = parse_json_file(json_path)
            
            # Parse patterns from JSON
            patterns = []
            for pattern_data in data.get('patterns', []):
                pattern = cls._parse_pattern(pattern_data)
                if pattern:
                    patterns.append(pattern)
            
            cls._patterns = patterns
            cls._loaded = True
            
            _log.info("Loaded %d patterns from %s", len(patterns), json_path)
            return True
            
        except ParseError as e:
            _log.error("Failed to load patterns from %s: %s", json_path, e)
            return False

    @classmethod
    def load_from_data(cls, patterns_data: List[dict]) -> bool:
        """Load patterns from a list of dictionaries.
        
        Args:
            patterns_data: List of pattern dictionaries.
            
        Returns:
            True if successful, False otherwise.
        """
        try:
            patterns = []
            for pattern_data in patterns_data:
                pattern = cls._parse_pattern(pattern_data)
                if pattern:
                    patterns.append(pattern)
            
            cls._patterns = patterns
            cls._loaded = True
            
            _log.info("Loaded %d patterns from data", len(patterns))
            return True
            
        except Exception as e:
            _log.error("Failed to load patterns from data: %s", e)
            return False

    @classmethod
    def _parse_pattern(cls, data: dict) -> Optional[FailurePattern]:
        """Parse a pattern from JSON data.
        
        Args:
            data: Pattern dictionary from JSON.
            
        Returns:
            FailurePattern object or None if invalid.
        """
        try:
            # Parse conditions
            conditions = []
            for cond_data in data.get('conditions', []):
                conditions.append(PatternCondition(
                    metric=cond_data['metric'],
                    op=cond_data['op'],
                    value=cond_data['value']
                ))
            
            # Parse actions
            actions = []
            for action_data in data.get('actions', []):
                actions.append(PatternAction(
                    id=action_data['id'],
                    parameter=action_data['parameter'],
                    type=action_data['type'],
                    factor=action_data.get('factor'),
                    delta=action_data.get('delta'),
                    value=action_data.get('value'),
                    bounds=tuple(action_data['bounds']) if 'bounds' in action_data else None
                ))
            
            return FailurePattern(
                id=data['id'],
                category=data['category'],
                conditions=conditions,
                actions=actions,
                description=data.get('description', ''),
                severity=data.get('severity', 0.5)
            )
            
        except (KeyError, TypeError) as e:
            _log.warning("Failed to parse pattern %s: %s", data.get('id', 'unknown'), e)
            return None

    @classmethod
    def get_all(cls) -> List[FailurePattern]:
        """Get all loaded patterns.
        
        Returns:
            List of all FailurePattern objects.
        """
        return cls._patterns

    @classmethod
    def get_by_category(cls, category: str) -> List[FailurePattern]:
        """Get patterns by category.
        
        Args:
            category: Pattern category (e.g., "risk", "frequency", "entries", etc.)
            
        Returns:
            List of matching FailurePattern objects.
        """
        return [p for p in cls._patterns if p.category == category]

    @classmethod
    def get_by_id(cls, pattern_id: str) -> Optional[FailurePattern]:
        """Get a pattern by ID.
        
        Args:
            pattern_id: The pattern identifier.
            
        Returns:
            FailurePattern object or None if not found.
        """
        for pattern in cls._patterns:
            if pattern.id == pattern_id:
                return pattern
        return None

    @classmethod
    def is_loaded(cls) -> bool:
        """Check if patterns have been loaded.
        
        Returns:
            True if patterns are loaded, False otherwise.
        """
        return cls._loaded

    @classmethod
    def get_categories(cls) -> List[str]:
        """Get all unique categories.
        
        Returns:
            List of category names.
        """
        return list(set(p.category for p in cls._patterns))

    @classmethod
    def count(cls) -> int:
        """Get total number of patterns.
        
        Returns:
            Number of loaded patterns.
        """
        return len(cls._patterns)

    @classmethod
    def clear(cls) -> None:
        """Clear all loaded patterns."""
        cls._patterns = []
        cls._loaded = False
        _log.info("Cleared pattern database")
