"""
UnifiedHandler — Profile 驱动的统一服务端处理器插件。

架构:
  Handler = Base（服务端适配，多选一） ⊕ Features（功能增强，可多选）

Profile 生命周期:
  1. 内置 profiles 存放于 resources/builtin_profiles/
  2. 首次加载时释放到 config/unified_handler/profiles/
  3. 用户可自由查看和修改
  4. 若用户删除了某个 profile，下次加载时重新释放
  5. 插件更新后若内置 profile 有新版，通过 logger.warning 提醒
  6. 用户删除旧版 profile 并重载即可获得新版
"""

import os
import shutil
import time
import zipfile
from typing import Optional, TYPE_CHECKING

from ruamel.yaml import YAML

from mcdreforged.api.all import PluginServerInterface
from mcdreforged.api.rtext import RTextList, RText, RStyle
from mcdreforged.minecraft.rtext.style import RColor
from mcdreforged.api.command import Literal

from .config import PluginConfig
_yaml = YAML(typ='safe')

from .handler import (
    UnifiedHandler,
    instantiate_handler,
    instantiate_handler_by_class_path,
    get_handler_from_mcdr_registry,
)
from .profile_loader import (
    load_feature_profiles,
    load_base_profile,
    load_yaml_profile,
    compile_features,
    compile_full_profile,
    is_newer_version,
)

if TYPE_CHECKING:
    from mcdreforged.handler.server_handler import ServerHandler

PLUGIN_ID = 'unified_handler'

_handler: Optional['UnifiedHandler'] = None
_config: Optional[PluginConfig] = None
_update_pending_at: Optional[float] = None

# =============================================================================
# Profile 同步
# =============================================================================

def _list_bundled_profiles() -> list[tuple[str, str, str]]:
    """
    List builtin profile files shipped with the plugin.

    Returns a list of (relative_path, profile_type, filename) tuples.
    Tries filesystem first (source mode), falls back to zip listing (.mcdr mode).
    """
    builtin_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'resources', 'builtin_profiles')

    # Source mode — filesystem listing
    if os.path.isdir(builtin_dir):
        result = []
        for profile_type in ['features', 'base']:
            type_dir = os.path.join(builtin_dir, profile_type)
            if os.path.isdir(type_dir):
                for filename in sorted(os.listdir(type_dir)):
                    if filename.endswith('.yml') and not filename.startswith('.'):
                        rel = f'resources/builtin_profiles/{profile_type}/{filename}'
                        result.append((rel, profile_type, filename))
        return result

    # .mcdr mode — zip listing
    mcdr_path = __file__
    while mcdr_path and not mcdr_path.endswith('.mcdr'):
        mcdr_path = os.path.dirname(mcdr_path)

    if mcdr_path and os.path.isfile(mcdr_path):
        result = []
        with zipfile.ZipFile(mcdr_path, 'r') as zf:
            for name in sorted(zf.namelist()):
                if not name.startswith('resources/builtin_profiles/') or not name.endswith('.yml'):
                    continue
                parts = name.split('/')
                if len(parts) >= 4:
                    profile_type = parts[2]  # 'base' or 'features'
                    filename = parts[3]
                    result.append((name, profile_type, filename))
        return result

    return []


def _read_bundled_yaml(server: PluginServerInterface, relative_path: str) -> Optional[dict]:
    """Read a YAML file from the plugin bundle. Returns None on failure."""
    try:
        with server.open_bundled_file(relative_path) as f:
            return _yaml.load(f.read().decode('utf-8'))
    except Exception:
        return None


def _get_user_profiles_dir(server: PluginServerInterface) -> str:
    """用户 profiles 目录（可编辑）"""
    return os.path.join(server.get_data_folder(), 'profiles')


def _sync_builtin_profiles(server: PluginServerInterface) -> None:
    """
    同步内置 profiles 到用户目录。

    - 缺失的 → 从内置释放
    - 已有的但内置版本更新 → 记录警告
    """
    bundled = _list_bundled_profiles()
    if not bundled:
        server.logger.warning(server.rtr(f'{PLUGIN_ID}.sync.builtin_dir_not_found', 'resources/builtin_profiles'))
        return

    user_dir = _get_user_profiles_dir(server)
    written_types: set[str] = set()
    outdated_count = 0

    for rel_path, profile_type, filename in bundled:
        user_type_dir = os.path.join(user_dir, profile_type)
        if profile_type not in written_types:
            os.makedirs(user_type_dir, exist_ok=True)
            written_types.add(profile_type)

        user_path = os.path.join(user_type_dir, filename)

        if not os.path.exists(user_path):
            with server.open_bundled_file(rel_path) as src:
                with open(user_path, 'wb') as dst:
                    shutil.copyfileobj(src, dst)
            server.logger.info(
                server.rtr(f'{PLUGIN_ID}.sync.installed_profile', profile_type, filename)
            )
        else:
            builtin_data = _read_bundled_yaml(server, rel_path)
            user_data = load_yaml_profile(user_path)
            if builtin_data and user_data:
                bv = builtin_data.get('version', '0')
                uv = user_data.get('version', '0')
                if is_newer_version(bv, uv):
                    name = builtin_data.get('name', filename)
                    changelog = builtin_data.get('changelog', '')
                    outdated_count += 1
                    server.logger.warning(
                        server.rtr(f'{PLUGIN_ID}.sync.update_available', name, uv, bv)
                    )
                    if changelog:
                        server.logger.warning(
                            server.rtr(f'{PLUGIN_ID}.sync.changelog_prefix', changelog)
                        )

    if outdated_count and _config is not None:
        server.logger.warning(
            server.rtr(f'{PLUGIN_ID}.sync.update_reminder', outdated_count, _config.command_prefix)
        )


def _deploy_schema(server: PluginServerInterface) -> None:
    """将内置的 profile.schema.json 部署到插件配置文件夹（始终覆盖）。"""
    schema_path = os.path.join(server.get_data_folder(), 'profile.schema.json')
    try:
        with server.open_bundled_file('profile.schema.json') as src:
            with open(schema_path, 'wb') as dst:
                shutil.copyfileobj(src, dst)
    except Exception:
        server.logger.warning(server.rtr(f'{PLUGIN_ID}.sync.schema_failed', schema_path))


def _find_outdated_profiles(server: PluginServerInterface) -> list:
    """找出所有内置版本比用户版本新的 profile。返回 [(rel_path, profile_type, filename, name, uv, bv, changelog), ...]"""
    bundled = _list_bundled_profiles()
    if not bundled:
        return []
    user_dir = _get_user_profiles_dir(server)
    outdated = []
    for rel_path, profile_type, filename in bundled:
        user_path = os.path.join(user_dir, profile_type, filename)
        if not os.path.exists(user_path):
            continue
        builtin_data = _read_bundled_yaml(server, rel_path)
        user_data = load_yaml_profile(user_path)
        if builtin_data and user_data:
            bv = builtin_data.get('version', '0')
            uv = user_data.get('version', '0')
            if is_newer_version(bv, uv):
                name = builtin_data.get('name', filename)
                changelog = builtin_data.get('changelog', '')
                outdated.append((rel_path, profile_type, filename, name, uv, bv, changelog))
    return outdated


def _overwrite_outdated_profiles(server: PluginServerInterface, outdated: list) -> None:
    """用内置版本覆盖过期的用户 profile 文件。"""
    user_dir = _get_user_profiles_dir(server)
    for rel_path, profile_type, filename, name, uv, bv, _changelog in outdated:
        user_path = os.path.join(user_dir, profile_type, filename)
        with server.open_bundled_file(rel_path) as src:
            with open(user_path, 'wb') as dst:
                shutil.copyfileobj(src, dst)
        server.logger.info(
            server.rtr(f'{PLUGIN_ID}.sync.updated_profile', name, uv, bv)
        )


# =============================================================================
# Handler 构建
# =============================================================================

def _resolve_handler_instance(name: str, server: PluginServerInterface) -> Optional['ServerHandler']:
    handler = instantiate_handler(name)
    if handler is not None:
        return handler
    handler = get_handler_from_mcdr_registry(name, server)
    if handler is not None:
        return handler
    handler = instantiate_handler_by_class_path(name)
    if handler is not None:
        return handler
    return None


def _resolve_base_handler(config: PluginConfig, server: PluginServerInterface) -> 'ServerHandler':
    base_name = config.base_handler
    if base_name == 'auto':
        mcdr_config = server.get_mcdr_config()
        base_name = mcdr_config.get('handler', 'basic_handler')
        server.logger.info(server.rtr(f'{PLUGIN_ID}.auto_detected', base_name))
    handler = _resolve_handler_instance(base_name, server)
    if handler is not None:
        server.logger.info(server.rtr(f'{PLUGIN_ID}.base_handler', base_name))
        return handler
    server.logger.warning(server.rtr(f'{PLUGIN_ID}.base_not_found', base_name))
    from mcdreforged.handler.impl import BasicHandler
    return BasicHandler()


def _build(server: PluginServerInterface, config: PluginConfig) -> UnifiedHandler:
    profiles_dir = _get_user_profiles_dir(server)

    # 加载 feature profiles
    feature_dicts = load_feature_profiles(profiles_dir, config.features)
    for name in config.features:
        found = any(fd.get('name') == name for fd in feature_dicts)
        if not found:
            server.logger.warning(server.rtr(f'{PLUGIN_ID}.feature_not_found', name))

    if config.base_handler in _list_base_names(profiles_dir):
        from mcdreforged.handler.impl import BasicHandler
        base_dict = load_base_profile(profiles_dir, config.base_handler)
        if base_dict is None:
            server.logger.error(server.rtr(f'{PLUGIN_ID}.base_profile_not_found', config.base_handler))
            handler = UnifiedHandler(BasicHandler(), compile_features(feature_dicts), mode='wrapper',
                                     logger=server.logger, debug=config.debug)
            _store_handler(handler)
            return handler

        extends = base_dict.get('extends')

        if extends:
            # Derived base — 继承已有 handler，叠加 profile 的覆写
            parent = _resolve_handler_instance(extends, server)
            if parent is None:
                server.logger.warning(server.rtr(f'{PLUGIN_ID}.extends_not_found', extends))
                parent = BasicHandler()
            else:
                server.logger.info(server.rtr(f'{PLUGIN_ID}.derived_base', config.base_handler, extends))
            mode = 'wrapper'
        else:
            # Full profile — 完全由 profile 定义（如 Bedrock）
            parent = BasicHandler()
            mode = 'full_profile'

        compiled = compile_full_profile(base_dict)
        for fd in feature_dicts:
            compiled.merge_feature(fd)
        server.logger.info(server.rtr(f'{PLUGIN_ID}.base_handler', config.base_handler))
        server.logger.info(server.rtr(f'{PLUGIN_ID}.features', ', '.join(config.features) or '(none)'))
        handler = UnifiedHandler(parent, compiled, mode=mode,
                                 logger=server.logger, debug=config.debug)
        _store_handler(handler)
        return handler

    # Wrapper 模式 — 内置或自定义 handler + feature 叠加
    base = _resolve_base_handler(config, server)
    compiled = compile_features(feature_dicts)
    server.logger.info(server.rtr(f'{PLUGIN_ID}.features', ', '.join(config.features) or '(none)'))
    server.logger.info(server.rtr(f'{PLUGIN_ID}.profile_loaded', len(feature_dicts)))
    handler = UnifiedHandler(base, compiled, mode='wrapper',
                             logger=server.logger, debug=config.debug)
    _store_handler(handler)
    return handler


def _store_handler(handler: UnifiedHandler) -> None:
    global _handler
    _handler = handler


def _list_base_names(profiles_dir: str) -> list:
    """列出可用的 base profile 名称"""
    from .profile_loader import list_available_profiles
    return list_available_profiles(profiles_dir, 'base')


# =============================================================================
# MCDR Entry Points
# =============================================================================

def on_load(server: PluginServerInterface, prev_module):
    global _config
    _config = server.load_config_simple(
        file_name='config.yml',
        target_class=PluginConfig,
    )

    # 同步内置 profiles
    _sync_builtin_profiles(server)

    # 部署 schema（始终覆盖，确保是最新版）
    _deploy_schema(server)

    # 构建并注册 handler
    handler = _build(server, _config)
    server.register_server_handler(handler)
    server.logger.info(server.rtr(f'{PLUGIN_ID}.handler_registered'))

    _register_commands(server)


def on_mcdr_stop(server: PluginServerInterface):
    if _handler is not None and _handler.is_debug_enabled():
        for line in _handler.get_lifecycle_status():
            server.logger.info(RText(line, color=RColor.gold).to_colored_text())


def _register_commands(server: PluginServerInterface):
    prefix = _config.command_prefix

    def cmd_status(src):
        base = _config.base_handler
        if base == 'auto':
            mcdr_config = server.get_mcdr_config()
            base = server.rtr(f'{PLUGIN_ID}.status.auto_format', mcdr_config.get('handler', '?'))
        features = ', '.join(_config.features) if _config.features else server.rtr(f'{PLUGIN_ID}.status.none')
        label_base = server.rtr(f'{PLUGIN_ID}.status.base')
        label_features = server.rtr(f'{PLUGIN_ID}.status.features')
        src.reply(RTextList(
            RText(server.rtr(f'{PLUGIN_ID}.status.title') + '\n', styles=RStyle.bold),
            server.rtr(f'{PLUGIN_ID}.status.line', label_base, base),
            server.rtr(f'{PLUGIN_ID}.status.line', label_features, features),
        ))

    def cmd_reload(src):
        if not src.has_permission(_config.admin_permission):
            src.reply(server.rtr(f'{PLUGIN_ID}.permission_denied'))
            return
        server.reload_plugin(PLUGIN_ID)

    def cmd_debug_toggle(src):
        if _handler is not None:
            new_state = not _handler.is_debug_enabled()
            _handler.set_debug(new_state)
            status_text = server.rtr(f'{PLUGIN_ID}.debug.on') if new_state else server.rtr(f'{PLUGIN_ID}.debug.off')
            src.reply(status_text)

    def cmd_debug_on(src):
        if _handler is not None:
            _handler.set_debug(True)
            src.reply(server.rtr(f'{PLUGIN_ID}.debug.on'))

    def cmd_debug_off(src):
        if _handler is not None:
            _handler.set_debug(False)
            src.reply(server.rtr(f'{PLUGIN_ID}.debug.off'))

    def cmd_update(src):
        global _update_pending_at
        outdated = _find_outdated_profiles(server)
        if not outdated:
            src.reply(server.rtr(f'{PLUGIN_ID}.update.none'))
            _update_pending_at = None
            return

        now = time.time()
        if _update_pending_at is not None and now - _update_pending_at <= 10:
            _overwrite_outdated_profiles(server, outdated)
            _update_pending_at = None
            server.reload_plugin(PLUGIN_ID)
            return

        _update_pending_at = now
        lines = [server.rtr(f'{PLUGIN_ID}.update.pending_header')]
        for _, _, _, name, uv, bv, _changelog in outdated:
            lines.append(server.rtr(f'{PLUGIN_ID}.update.pending_item', name, uv, bv))
        lines.append(server.rtr(f'{PLUGIN_ID}.update.pending_footer', prefix))
        src.reply(RTextList(*[RText(line + '\n') for line in lines]))

    server.register_command(
        Literal(prefix).runs(cmd_status).then(
            Literal('reload').requires(
                lambda src: src.has_permission(_config.admin_permission),
                failure_message_getter=lambda: server.rtr(f'{PLUGIN_ID}.permission_denied'),
            ).runs(cmd_reload)
        ).then(
            Literal('status').runs(cmd_status)
        ).then(
            Literal('debug').runs(cmd_debug_toggle).then(
                Literal('on').runs(cmd_debug_on)
            ).then(
                Literal('off').runs(cmd_debug_off)
            )
        ).then(
            Literal('update').requires(
                lambda src: src.has_permission(_config.admin_permission),
                failure_message_getter=lambda: server.rtr(f'{PLUGIN_ID}.permission_denied'),
            ).runs(cmd_update)
        )
    )
    server.register_help_message(prefix, server.rtr(f'{PLUGIN_ID}.help.unified_handler'))
    server.register_help_message(prefix + ' debug', server.rtr(f'{PLUGIN_ID}.help.debug'))
    server.register_help_message(prefix + ' update', server.rtr(f'{PLUGIN_ID}.help.update'))
