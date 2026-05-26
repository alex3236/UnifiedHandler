"""Shared helpers for profile tests.

Assumes UnifiedHandler is the repo root: resources/builtin_profiles/ at project root.
MCDR is an installed dependency, not a sibling directory.
"""
import os
import sys
from typing import Optional, Tuple

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)

from mcdreforged.handler.server_handler import ServerHandler

from unified_handler.handler import UnifiedHandler
from unified_handler.profile_loader import (
    load_yaml_profile,
    compile_features,
    compile_full_profile,
    CompiledProfile,
)

_BUILTIN = os.path.join(_root, 'resources', 'builtin_profiles')


def load_profile(name: str, profile_type: str = 'features') -> dict:
    path = os.path.join(_BUILTIN, profile_type, f'{name}.yml')
    data = load_yaml_profile(path)
    if data is None:
        raise FileNotFoundError(f'Profile not found: {path}')
    return data


def make_handler(
    profile_dict: dict, base: ServerHandler, mode: str = 'wrapper'
) -> UnifiedHandler:
    compiled = CompiledProfile()
    compiled.merge_feature(profile_dict)
    return UnifiedHandler(base, compiled, mode=mode)


def parse_line(handler: UnifiedHandler, text: str):
    pre = handler.pre_parse_server_stdout(text)
    return handler.parse_server_stdout(pre)
