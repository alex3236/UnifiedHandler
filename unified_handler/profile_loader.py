"""
Profile 加载与编译。

从 config/unified_handler/profiles/ 目录加载 YAML profile 文件，
解析后预编译所有正则表达式为 CompiledProfile。
"""

import os
import re
from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Dict

from ruamel.yaml import YAML

_yaml = YAML()


# =============================================================================
# CompiledProfile — 预编译的运行时结构
# =============================================================================

@dataclass
class CompiledProfile:
    """编译后的 profile，所有正则预编译，运行时零解析开销"""

    # ── log_format ──
    log_format_patterns: List[re.Pattern] = field(default_factory=list)

    # ── pre_parse ──
    pre_parse_subs: List[Tuple[re.Pattern, str, bool]] = field(default_factory=list)  # (pattern, replacement, stop_on_match)
    pre_strip_ansi: bool = False
    pre_strip_control_chars: bool = False
    pre_control_chars_except: List[str] = field(default_factory=list)

    # ── player message ──
    player_patterns: List[re.Pattern] = field(default_factory=list)
    player_name_regex: Optional[re.Pattern] = None
    quote_player_names: bool = False
    ignore_content_prefixes: List[str] = field(default_factory=list)
    player_extra_fields: Dict[str, str] = field(default_factory=dict)  # capture_group → info_attribute
    player_message_subs: List[Tuple[re.Pattern, str, bool]] = field(default_factory=list)  # (pattern, replacement, stop_on_match)

    # ── pseudo players ──
    pseudo_players: List[Tuple[re.Pattern, str]] = field(default_factory=list)

    # ── player join / leave ──
    join_patterns: List[re.Pattern] = field(default_factory=list)
    left_patterns: List[re.Pattern] = field(default_factory=list)

    # ── server state detection ──
    version_pattern: Optional[re.Pattern] = None
    address_pattern: Optional[re.Pattern] = None
    address_first_only: bool = False
    startup_patterns: List[re.Pattern] = field(default_factory=list)
    rcon_pattern: Optional[re.Pattern] = None
    rcon_disabled: bool = False
    stopping_patterns: List[re.Pattern] = field(default_factory=list)

    # ── commands ──
    stop_command: Optional[str] = None
    send_message_template: Optional[str] = None
    broadcast_template: Optional[str] = None
    message_format: str = "java_json"

    def merge_feature(self, raw: dict) -> None:
        """将一个 feature profile 的原始 dict 合并进来"""
        # log_format
        if 'log_format' in raw:
            lf = raw['log_format']
            if 'patterns' in lf:
                self.log_format_patterns.extend(_compile_patterns(lf['patterns']))
            elif 'pattern' in lf:
                self.log_format_patterns.append(re.compile(lf['pattern']))

        # pre_parse
        if 'pre_parse' in raw:
            pp = raw['pre_parse']
            if pp.get('strip_ansi'):
                self.pre_strip_ansi = True
            if pp.get('strip_control_chars'):
                self.pre_strip_control_chars = True
            for exc in pp.get('control_chars_except', []):
                if exc not in self.pre_control_chars_except:
                    self.pre_control_chars_except.append(exc)
            for sub in pp.get('regex_substitutions', []):
                self.pre_parse_subs.append((
                    re.compile(sub['pattern']),
                    sub.get('replacement', ''),
                    sub.get('stop_on_match', False)
                ))

        # player_message
        if 'player_message' in raw:
            pm = raw['player_message']
            for p in pm.get('patterns', []):
                self.player_patterns.append(re.compile(p) if isinstance(p, str) else p)
            if 'name_validation' in pm:
                self.player_name_regex = re.compile(pm['name_validation'])
            if 'quote_player_names' in pm:
                self.quote_player_names = pm['quote_player_names']
            for prefix in pm.get('ignore_content_prefixes', []):
                if prefix not in self.ignore_content_prefixes:
                    self.ignore_content_prefixes.append(prefix)
            for capture_group, attr_name in pm.get('extra_fields', {}).items():
                self.player_extra_fields[capture_group] = attr_name
            for sub in pm.get('regex_substitutions', []):
                self.player_message_subs.append((
                    re.compile(sub['pattern']),
                    sub.get('replacement', ''),
                    sub.get('stop_on_match', False)
                ))

        # pseudo_players (nested under parse_server_stdout)
        if 'parse_server_stdout' in raw:
            pss = raw['parse_server_stdout']
            for pp_data in pss.get('pseudo_players', []):
                self.pseudo_players.append((
                    re.compile(pp_data['pattern']),
                    pp_data['player_name']
                ))

        # join/left
        for p in raw.get('player_joined', {}).get('patterns', []):
            self.join_patterns.append(re.compile(p))
        for p in raw.get('player_left', {}).get('patterns', []):
            self.left_patterns.append(re.compile(p))

        # server state
        if 'server_version' in raw:
            self.version_pattern = re.compile(raw['server_version']['pattern'])
        if 'server_address' in raw:
            sa = raw['server_address']
            self.address_pattern = re.compile(sa['pattern'])
            if sa.get('detection_mode') == 'first_only':
                self.address_first_only = True
        for p in raw.get('server_startup_done', {}).get('patterns', []):
            self.startup_patterns.append(re.compile(p))
        if 'rcon_started' in raw:
            r = raw['rcon_started']
            if r.get('enabled') is False:
                self.rcon_disabled = True
            elif 'pattern' in r:
                self.rcon_pattern = re.compile(r['pattern'])
        for p in raw.get('server_stopping', {}).get('patterns', []):
            self.stopping_patterns.append(re.compile(p))

        # commands
        if 'commands' in raw:
            cmd = raw['commands']
            if 'stop' in cmd:
                self.stop_command = cmd['stop']
            if 'send_message' in cmd:
                self.send_message_template = cmd['send_message'].get('template')
            if 'broadcast' in cmd:
                self.broadcast_template = cmd['broadcast'].get('template')
            if 'message_format' in cmd:
                self.message_format = cmd['message_format']


# =============================================================================
# Profile 加载
# =============================================================================

def load_yaml_profile(path: str) -> Optional[dict]:
    """加载单个 YAML profile 文件为 dict"""
    if not os.path.isfile(path):
        return None
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return _yaml.load(f)
    except Exception:
        return None


def load_feature_profiles(profiles_dir: str, names: List[str]) -> List[dict]:
    """从目录加载指定名称的 feature profiles"""
    result = []
    features_dir = os.path.join(profiles_dir, 'features')
    for name in names:
        path = os.path.join(features_dir, f'{name}.yml')
        data = load_yaml_profile(path)
        if data is not None:
            result.append(data)
    return result


def load_base_profile(profiles_dir: str, name: str) -> Optional[dict]:
    """加载 base profile"""
    path = os.path.join(profiles_dir, 'base', f'{name}.yml')
    return load_yaml_profile(path)


def list_available_profiles(profiles_dir: str, profile_type: str) -> List[str]:
    """列出 profiles 目录下所有可用的 profile 名称（不含 .yml 后缀）"""
    target_dir = os.path.join(profiles_dir, profile_type)
    if not os.path.isdir(target_dir):
        return []
    return sorted([
        os.path.splitext(f)[0]
        for f in os.listdir(target_dir)
        if f.endswith('.yml') and not f.startswith('.')
    ])


def compile_features(feature_dicts: List[dict]) -> CompiledProfile:
    """将多个 feature profile dict 编译为单一 CompiledProfile"""
    compiled = CompiledProfile()
    for fd in feature_dicts:
        compiled.merge_feature(fd)
    return compiled


def compile_full_profile(profile_dict: dict) -> CompiledProfile:
    """编译完整 base profile"""
    compiled = CompiledProfile()
    compiled.merge_feature(profile_dict)
    return compiled


# =============================================================================
# Helpers
# =============================================================================

def _compile_patterns(patterns: list) -> List[re.Pattern]:
    return [re.compile(p) if isinstance(p, str) else p for p in patterns]


def _version_tuple(v: str) -> tuple:
    try:
        return tuple(int(x) for x in v.split('.'))
    except (ValueError, AttributeError):
        return (0,)


def is_newer_version(builtin_version: str, user_version: str) -> bool:
    """判断 builtin 版本是否比 user 版本更新"""
    return _version_tuple(builtin_version) > _version_tuple(user_version)
