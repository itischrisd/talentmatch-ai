from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any


def read_toml(path: Path) -> dict[str, Any]:
    """
    Read a TOML file into a dictionary
    :param path: path to the TOML file
    :return: dictionary with the TOML contents
    """

    with path.open("rb") as file:
        return tomllib.load(file)


def read_settings_toml(entry_path: Path) -> dict[str, Any]:
    """
    Read a settings entry TOML and merge any included fragments
    :param entry_path: path to the main settings TOML file
    :return: merged settings dictionary
    """

    entry = read_toml(entry_path)
    merged: dict[str, Any] = {}

    for include in _extract_includes(entry):
        fragment_path = (entry_path.parent / include).resolve()
        merged = _deep_merge(merged, read_toml(fragment_path))

    merged = _deep_merge(merged, _drop_settings_metadata(entry))
    return merged


def _extract_includes(entry: dict[str, Any]) -> list[str]:
    settings_meta = entry.get("settings")
    includes: list[str] = []
    if isinstance(settings_meta, dict):
        raw_includes = settings_meta.get("includes", [])
        if isinstance(raw_includes, list):
            includes.extend([str(item) for item in raw_includes])
    return includes


def _drop_settings_metadata(entry: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in entry.items() if key != "settings"}


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged: dict[str, Any] = dict(base)
    for key, override_value in override.items():
        base_value = merged.get(key)
        if isinstance(base_value, dict) and isinstance(override_value, dict):
            merged[key] = _deep_merge(base_value, override_value)
        else:
            merged[key] = override_value
    return merged
