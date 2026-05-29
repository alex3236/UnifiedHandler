import json
import re
from typing import Optional, Tuple, List, Dict

from mcdreforged.handler.server_handler import ServerHandler
from mcdreforged.handler.impl import *
from mcdreforged.info_reactor.info import Info, InfoSource
from mcdreforged.info_reactor.server_information import ServerInformation
from mcdreforged.minecraft.rtext.style import RColor
from mcdreforged.minecraft.rtext.text import RText
from mcdreforged.utils import string_utils
from mcdreforged.utils.types.message import MessageText

from .profile_loader import CompiledProfile

# =============================================================================
# Handler name → class 映射（用于从 MCDR 配置名称实例化 handler）
# =============================================================================

_HANDLER_CLASS_MAP: Dict[str, type] = {
    'basic_handler': BasicHandler,
    'vanilla_handler': VanillaHandler,
    'forge_handler': ForgeHandler,
    'bukkit_handler': BukkitHandler,
    'bukkit14_handler': Bukkit14Handler,
    'cat_server_handler': CatServerHandler,
    'arclight_handler': ArclightHandler,
    'beta18_handler': Beta18Handler,
    'bungeecord_handler': BungeecordHandler,
    'waterfall_handler': WaterfallHandler,
    'velocity_handler': VelocityHandler,
}

_DEFAULT_PLAYER_NAME_REGEX = re.compile(r'[a-zA-Z0-9_]{3,16}')


def instantiate_handler(handler_name: str) -> Optional[ServerHandler]:
    """通过名称实例化 MCDR handler"""
    cls = _HANDLER_CLASS_MAP.get(handler_name)
    if cls is not None:
        return cls()
    return None


def instantiate_handler_by_class_path(class_path: str) -> Optional[ServerHandler]:
    """通过完整类路径实例化自定义 handler"""
    try:
        from mcdreforged.utils import class_utils
        cls = class_utils.load_class(class_path)
        if issubclass(cls, ServerHandler):
            return cls()
    except Exception:
        pass
    return None


def get_handler_from_mcdr_registry(handler_name: str, server) -> Optional[ServerHandler]:
    """从 MCDR 的 ServerHandlerManager 注册表中按名称获取 handler 实例。
    用于获取通过 MCDR custom_handlers 配置注册的自定义 handler。"""
    try:
        manager = server._mcdr_server.server_handler_manager
        return manager.handlers.get(handler_name)
    except Exception:
        return None


# =============================================================================
# UnifiedHandler
# =============================================================================

class UnifiedHandler(ServerHandler):
    """
    统一 handler。

    模式：
    - Wrapper（wrapper）：Base 是真正的 MCDR handler（内置或自定义）。Delegate + feature 叠加。
    - Full Profile（full_profile）：Base 是 BasicHandler。完全由 profile 驱动所有 13 个方法。
    """

    def __init__(self, base: ServerHandler, compiled: CompiledProfile,
                 mode: str = 'wrapper', logger=None, debug: bool = False):
        self._base = base
        self._c = compiled
        self._mode = mode  # 'wrapper' | 'full_profile'
        self._address_detected = False
        self._logger = logger
        self._debug = debug
        self._log_format_miss_count = 0
        self._log_format_miss_threshold = 10
        self._debug_player_source = None  # 'base' | 'profile' | 'pseudo' | None
        # lifecycle tracking (always on, negligible overhead)
        self._detected_version = False
        self._detected_startup = False
        self._detected_rcon = False
        self._detected_stopping = False
        self._detected_send_msg = 0
        self._detected_broadcast = 0

    def set_debug(self, enabled: bool) -> None:
        self._debug = enabled
        self._log_format_miss_count = 0

    def is_debug_enabled(self) -> bool:
        return self._debug

    def _debug_log(self, msg: str) -> None:
        if self._debug and self._logger is not None:
            self._logger.info(RText(msg, color=RColor.gold).to_colored_text())

    # ──────────────────────────────────────────
    # Basic Information
    # ──────────────────────────────────────────

    def get_name(self) -> str:
        return 'unified_handler'

    # ──────────────────────────────────────────
    # Server Control
    # ──────────────────────────────────────────

    def get_stop_command(self) -> str:
        if self._c.stop_command is not None:
            return self._c.stop_command
        return self._base.get_stop_command()

    def get_send_message_command(
        self, target: str, message: MessageText,
        server_information: ServerInformation
    ) -> Optional[str]:
        if self._c.send_message_template is not None:
            self._detected_send_msg += 1
            if self._debug:
                self._debug_log('send_msg: template used')
            return self._build_message_command(
                self._c.send_message_template, target, message, server_information
            )
        return self._base.get_send_message_command(target, message, server_information)

    def get_broadcast_message_command(
        self, message: MessageText, server_information: ServerInformation
    ) -> Optional[str]:
        if self._c.broadcast_template is not None:
            self._detected_broadcast += 1
            if self._debug:
                self._debug_log('broadcast: template used')
            return self._build_message_command(
                self._c.broadcast_template, '@a', message, server_information
            )
        return self._base.get_broadcast_message_command(message, server_information)

    # ──────────────────────────────────────────
    # Server Output Parsing
    # ──────────────────────────────────────────

    _ANSI_PATTERN = re.compile(r'\x1b\[[0-9;]*[A-Za-z]')

    def pre_parse_server_stdout(self, text: str) -> str:
        text = self._base.pre_parse_server_stdout(text)
        if self._c.pre_strip_ansi:
            text = self._ANSI_PATTERN.sub('', text)
        if self._c.pre_strip_control_chars:
            keep = set(self._c.pre_control_chars_except)
            text = ''.join(c for c in text if ord(c) >= 0x20 or c in keep)
        for i, (pattern, replacement, stop) in enumerate(self._c.pre_parse_subs):
            new_text = pattern.sub(replacement, text)
            if new_text != text:
                if self._debug:
                    before = text[:60] + ('...' if len(text) > 60 else '')
                    after = new_text[:60] + ('...' if len(new_text) > 60 else '')
                    self._debug_log('regex_sub[{}]: "{}" -> "{}"'.format(i, before, after))
                text = new_text
                if stop:
                    break
        return text

    def parse_console_command(self, text: str) -> Info:
        return self._base.parse_console_command(text)

    def parse_server_stdout(self, text: str) -> Info:
        # Full profile mode: always use profile's log_format
        if self._mode == 'full_profile' and self._c.log_format_patterns:
            info = self._raw_parse(text)
            self._apply_log_format(info, text)
        else:
            # Wrapper mode: delegate to base
            try:
                info = self._base.parse_server_stdout(text)
            except Exception:
                # Base failed — try feature log_format as fallback
                if self._c.log_format_patterns:
                    info = self._raw_parse(text)
                    self._apply_log_format(info, text)
                else:
                    info = self._raw_parse(text)

        self._debug_player_source = None

        if info.content is not None:
            if info.player is not None:
                self._debug_player_source = 'base'
            self._apply_content_filters(info)
            profile_matched = self._apply_player_patterns(info)
            if not profile_matched:
                self._apply_pseudo_players(info)

            if self._debug and info.player is not None:
                if self._debug_player_source == 'base':
                    msg = info.content or ''
                    self._debug_log('player_msg: "{}" "{}" (base)'.format(
                        info.player, msg[:60]))

        return info

    def parse_player_joined(self, info: Info) -> Optional[str]:
        result = self._base.parse_player_joined(info)
        if result is not None:
            if self._debug:
                self._debug_log('player_joined: "{}" (base)'.format(result))
            return result
        if info.content is not None and not info.is_user:
            for i, pattern in enumerate(self._c.join_patterns):
                m = pattern.fullmatch(info.content)
                if m is not None:
                    name = m['name']
                    if self._check_player_name(name):
                        if self._debug:
                            self._debug_log('player_joined: "{}" (profile #{})'.format(name, i + 1))
                        return name
        return None

    def parse_player_left(self, info: Info) -> Optional[str]:
        result = self._base.parse_player_left(info)
        if result is not None:
            if self._debug:
                self._debug_log('player_left: "{}" (base)'.format(result))
            return result
        if info.content is not None and not info.is_user:
            for i, pattern in enumerate(self._c.left_patterns):
                m = pattern.fullmatch(info.content)
                if m is not None:
                    name = m['name']
                    if self._check_player_name(name):
                        if self._debug:
                            self._debug_log('player_left: "{}" (profile #{})'.format(name, i + 1))
                        return name
        return None

    def parse_server_version(self, info: Info) -> Optional[str]:
        if self._c.version_pattern is not None:
            if info.content is not None and not info.is_user:
                m = self._c.version_pattern.fullmatch(info.content)
                if m is not None:
                    version = m['version']
                    self._detected_version = True
                    if self._debug:
                        self._debug_log('server_version: "{}" (profile)'.format(version))
                    return version
        result = self._base.parse_server_version(info)
        if result is not None:
            self._detected_version = True
            if self._debug:
                self._debug_log('server_version: "{}" (base)'.format(result))
        return result

    def parse_server_address(self, info: Info) -> Optional[Tuple[str, int]]:
        if self._c.address_pattern is not None:
            if self._c.address_first_only and self._address_detected:
                return None
            if info.content is not None and not info.is_user:
                m = self._c.address_pattern.fullmatch(info.content)
                if m is not None:
                    self._address_detected = True
                    ip = m.group('ip') if 'ip' in m.groupdict() else '127.0.0.1'
                    if self._debug:
                        flag = ' [first_only]' if self._c.address_first_only else ''
                        self._debug_log('server_address: {}:{}{} (profile)'.format(ip, m['port'], flag))
                    return ip, int(m['port'])
        result = self._base.parse_server_address(info)
        if self._debug and result is not None:
            self._debug_log('server_address: {}:{} (base)'.format(result[0], result[1]))
        return result

    def test_server_startup_done(self, info: Info) -> bool:
        if info.content is not None and info.is_from_server:
            for pattern in self._c.startup_patterns:
                if pattern.fullmatch(info.content) is not None:
                    self._detected_startup = True
                    if self._debug:
                        self._debug_log('startup_done: matched (profile)')
                    return True
        result = self._base.test_server_startup_done(info)
        if result:
            self._detected_startup = True
            if self._debug:
                self._debug_log('startup_done: matched (base)')
        return result

    def test_rcon_started(self, info: Info) -> bool:
        if self._c.rcon_disabled:
            return False
        if self._c.rcon_pattern is not None:
            matched = (
                info.content is not None
                and info.is_from_server
                and self._c.rcon_pattern.fullmatch(info.content) is not None
            )
            if matched:
                self._detected_rcon = True
                if self._debug:
                    self._debug_log('rcon: matched (profile)')
            return matched
        result = self._base.test_rcon_started(info)
        if result:
            self._detected_rcon = True
            if self._debug:
                self._debug_log('rcon: matched (base)')
        return result

    def test_server_stopping(self, info: Info) -> bool:
        if info.content is not None and info.is_from_server:
            for pattern in self._c.stopping_patterns:
                if pattern.fullmatch(info.content) is not None:
                    self._detected_stopping = True
                    if self._debug:
                        self._debug_log('server_stopping: matched (profile)')
                    return True
        result = self._base.test_server_stopping(info)
        if result:
            self._detected_stopping = True
            if self._debug:
                self._debug_log('server_stopping: matched (base)')
        return result

    # ──────────────────────────────────────────
    # Lifecycle Report
    # ──────────────────────────────────────────

    def get_lifecycle_status(self) -> list:
        lines = ['=== Lifecycle Status ===']
        ok = '\u221a'
        no = '\u00d7'

        version_str = self._detected_version
        lines.append('  server_version:     {}'.format(ok if version_str else no))

        addr_str = self._address_detected
        lines.append('  server_address:     {}'.format(ok if addr_str else no))

        startup_str = self._detected_startup
        lines.append('  startup_done:       {}'.format(ok if startup_str else no))

        rcon_str = 'disabled' if self._c.rcon_disabled else self._detected_rcon
        if self._c.rcon_disabled:
            lines.append('  rcon_started:       disabled')
        else:
            lines.append('  rcon_started:       {}'.format(ok if rcon_str else no))

        stopping_str = self._detected_stopping
        lines.append('  server_stopping:    {}'.format(ok if stopping_str else no))

        if self._c.send_message_template is not None:
            lines.append('  send_msg (profile): used {} time(s)'.format(self._detected_send_msg))
        if self._c.broadcast_template is not None:
            lines.append('  broadcast (profile): used {} time(s)'.format(self._detected_broadcast))
        if self._c.stop_command is not None:
            lines.append('  stop_command:        "{}"'.format(self._c.stop_command))

        lines.append('======================')
        return lines

    # ──────────────────────────────────────────
    # Internal Helpers
    # ──────────────────────────────────────────

    def _check_player_name(self, name: str) -> bool:
        regex = self._c.player_name_regex or _DEFAULT_PLAYER_NAME_REGEX
        return regex.fullmatch(name) is not None

    @staticmethod
    def _raw_parse(text: str) -> Info:
        if not isinstance(text, str):
            raise TypeError('The text to parse should be a string')
        result = Info(InfoSource.SERVER, text)
        result.content = string_utils.clean_console_color_code(text)
        return result

    def _apply_log_format(self, info: Info, text: str) -> None:
        raw = info.content if info.content is not None else text
        for pattern in self._c.log_format_patterns:
            m = pattern.fullmatch(raw)
            if m is not None:
                gd = m.groupdict()
                info.hour = int(gd['hour'])
                info.min = int(gd['min'])
                info.sec = int(gd['sec'])
                info.logging_level = gd['logging']
                info.content = gd['content']
                if self._debug:
                    self._log_format_miss_count = 0
                return
        if self._debug:
            self._log_format_miss_count += 1
            if self._log_format_miss_count >= self._log_format_miss_threshold:
                display = raw[:80] + ('...' if len(raw) > 80 else '')
                self._debug_log('log_format: {} lines unmatched; last: "{}"'.format(
                    self._log_format_miss_count, display))
                self._log_format_miss_count = 0

    def _apply_content_filters(self, info: Info) -> None:
        for prefix in self._c.ignore_content_prefixes:
            if info.content.startswith(prefix):
                if self._debug:
                    self._debug_log('content_filtered: prefix="{}"'.format(prefix))
                info.content = ""
                return

    def _apply_player_patterns(self, info: Info) -> bool:
        if info.player is not None:
            return False
        for i, pattern in enumerate(self._c.player_patterns):
            m = pattern.fullmatch(info.content)
            if m is not None and 'name' in m.groupdict():
                name = m['name']
                if self._check_player_name(name):
                    info.player = name
                    if self._c.quote_player_names:
                        info.player = '"' + info.player + '"'
                    if 'message' in m.groupdict():
                        info.content = m['message']
                    self._attach_extra_fields(info, m.groupdict(), self._c.player_extra_fields)
                    self._apply_player_message_subs(info)
                    if self._debug:
                        self._debug_player_source = 'profile'
                        msg = info.content or ''
                        self._debug_log('player_msg: "{}" "{}" (profile #{})'.format(
                            info.player, msg[:60], i + 1))
                    return True
        return False

    def _apply_pseudo_players(self, info: Info) -> None:
        if info.player is not None:
            return
        for pattern, player_name in self._c.pseudo_players:
            m = pattern.fullmatch(info.content)
            if m is not None:
                info.player = player_name
                if 'message' in m.groupdict():
                    info.content = m['message']
                self._attach_extra_fields(info, m.groupdict(), self._c.player_extra_fields)
                if self._debug:
                    self._debug_player_source = 'pseudo'
                    msg = info.content or ''
                    self._debug_log('pseudo_player: "{}" "{}"'.format(
                        player_name, msg[:60]))
                return

    def _attach_extra_fields(self, info: Info, groupdict: dict, extra_fields: dict) -> None:
        for capture_group, attr_name in extra_fields.items():
            if capture_group in groupdict:
                value = groupdict[capture_group]
                setattr(info, attr_name, value)
                if self._debug:
                    self._debug_log('extra_field: {}="{}"'.format(attr_name, value))

    def _apply_player_message_subs(self, info: Info) -> None:
        if info.content is None:
            return
        for pattern, replacement, stop in self._c.player_message_subs:
            result = pattern.sub(replacement, info.content)
            if result != info.content:
                if self._debug:
                    before = info.content[:60] + ('...' if len(info.content) > 60 else '')
                    after = result[:60] + ('...' if len(result) > 60 else '')
                    self._debug_log('player_msg_sub: "{}" -> "{}"'.format(before, after))
                info.content = result
                if stop:
                    return

    def _build_message_command(
        self, template: str, target: str, message: MessageText,
        server_information: ServerInformation
    ) -> str:
        formatted = self._format_message(message)
        return template.replace('{target}', target).replace('{message}', formatted)

    def _format_message(self, message: MessageText) -> str:
        if self._c.message_format == 'bedrock_rawtext':
            return self._format_bedrock_rawtext(message)
        # java_json (default)
        from mcdreforged.minecraft.rtext.text import RTextBase
        if isinstance(message, RTextBase):
            return message.to_json_str()
        return json.dumps(str(message), ensure_ascii=False)

    @staticmethod
    def _format_bedrock_rawtext(message: MessageText) -> str:
        from mcdreforged.minecraft.rtext.text import RTextBase
        if isinstance(message, RTextBase):
            if hasattr(message, 'to_legacy_text'):
                text = message.to_legacy_text()
            else:
                text = str(message)
            text = re.sub(r'\[↻]|\[↓]|\[×]|\[✎]|\[>]', '', text)
        else:
            text = str(message)
        lines = text.splitlines()
        rawtext = []
        for line in lines:
            rawtext.append({"text": line})
            rawtext.append({"text": "\n"})
        if rawtext and rawtext[-1] == {"text": "\n"}:
            rawtext.pop()
        return json.dumps({"rawtext": rawtext}, ensure_ascii=False)
