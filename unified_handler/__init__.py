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
import zipfile
import yaml
from typing import Optional, TYPE_CHECKING

from mcdreforged.api.all import PluginServerInterface
from mcdreforged.api.rtext import RTextList, RText, RStyle
from mcdreforged.api.command import Literal

from .config import PluginConfig
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
            return yaml.safe_load(f.read().decode('utf-8'))
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

    for rel_path, profile_type, filename in bundled:
        user_type_dir = os.path.join(user_dir, profile_type)
        if profile_type not in written_types:
            os.makedirs(user_type_dir, exist_ok=True)
            written_types.add(profile_type)

        user_path = os.path.join(user_type_dir, filename)

        if not os.path.exists(user_path):
            # 缺失 → 释放
            with server.open_bundled_file(rel_path) as src:
                with open(user_path, 'wb') as dst:
                    shutil.copyfileobj(src, dst)
            server.logger.info(
                server.rtr(f'{PLUGIN_ID}.sync.installed_profile', profile_type, filename)
            )
        else:
            # 检查版本
            builtin_data = _read_bundled_yaml(server, rel_path)
            user_data = load_yaml_profile(user_path)
            if builtin_data and user_data:
                bv = builtin_data.get('version', '0')
                uv = user_data.get('version', '0')
                if is_newer_version(bv, uv):
                    name = builtin_data.get('name', filename)
                    changelog = builtin_data.get('changelog', '')
                    server.logger.warning(
                        server.rtr(f'{PLUGIN_ID}.sync.update_available', name, uv, bv)
                    )
                    if changelog:
                        server.logger.warning(
                            server.rtr(f'{PLUGIN_ID}.sync.changelog_prefix', changelog)
                        )
                    server.logger.warning(
                        server.rtr(f'{PLUGIN_ID}.sync.update_instruction', user_path)
                    )


# =============================================================================
# Handler 构建
# =============================================================================

def _get_config(server: PluginServerInterface) -> PluginConfig:
    return server.load_config_simple(
        file_name='config.yml',
        target_class=PluginConfig,
    )


def _resolve_handler_instance(name: str, server: PluginServerInterface) -> Optional['ServerHandler']:
    """尝试解析 handler 名称为实例。返回 None 表示未找到。"""
    # 内置 handler class map
    handler = instantiate_handler(name)
    if handler is not None:
        return handler

    # MCDR 注册表（custom_handlers）
    handler = get_handler_from_mcdr_registry(name, server)
    if handler is not None:
        return handler

    # Python 类路径
    handler = instantiate_handler_by_class_path(name)
    if handler is not None:
        return handler

    return None


def _resolve_base_handler(config: PluginConfig, server: PluginServerInterface) -> 'ServerHandler':
    """解析 base handler（wrapper 模式下使用），含日志和回退"""
    base_name = config.base_handler

    if base_name == 'auto':
        mcdr_config = server.get_mcdr_config()
        base_name = mcdr_config.get('handler', 'basic_handler')
        server.logger.info(server.rtr(f'{PLUGIN_ID}.auto_detected', base_name))

    handler = _resolve_handler_instance(base_name, server)
    if handler is not None:
        server.logger.info(server.rtr(f'{PLUGIN_ID}.base_handler', base_name))
        return handler

    # 回退
    server.logger.warning(server.rtr(f'{PLUGIN_ID}.base_not_found', base_name))
    from mcdreforged.handler.impl import BasicHandler
    return BasicHandler()


def _build(server: PluginServerInterface) -> UnifiedHandler:
    config = _get_config(server)
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
            return UnifiedHandler(BasicHandler(), compile_features(feature_dicts), mode='wrapper')

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
        return UnifiedHandler(parent, compiled, mode=mode)

    # Wrapper 模式 — 内置或自定义 handler + feature 叠加
    base = _resolve_base_handler(config, server)
    compiled = compile_features(feature_dicts)
    server.logger.info(server.rtr(f'{PLUGIN_ID}.features', ', '.join(config.features) or '(none)'))
    server.logger.info(server.rtr(f'{PLUGIN_ID}.profile_loaded', len(feature_dicts)))
    return UnifiedHandler(base, compiled, mode='wrapper')


def _list_base_names(profiles_dir: str) -> list:
    """列出可用的 base profile 名称"""
    from .profile_loader import list_available_profiles
    return list_available_profiles(profiles_dir, 'base')


# =============================================================================
# MCDR Entry Points
# =============================================================================

def on_load(server: PluginServerInterface, prev_module):
    # 同步内置 profiles
    _sync_builtin_profiles(server)

    # 构建并注册 handler
    handler = _build(server)
    server.register_server_handler(handler)
    server.logger.info(server.rtr(f'{PLUGIN_ID}.handler_registered'))

    _register_commands(server)


def _register_commands(server: PluginServerInterface):
    cfg = _get_config(server)
    prefix = cfg.command_prefix

    def cmd_status(src):
        c = _get_config(server)
        base = c.base_handler
        if base == 'auto':
            mcdr_config = server.get_mcdr_config()
            base = server.rtr(f'{PLUGIN_ID}.status.auto_format', mcdr_config.get('handler', '?'))
        features = ', '.join(c.features) if c.features else server.rtr(f'{PLUGIN_ID}.status.none')
        label_base = server.rtr(f'{PLUGIN_ID}.status.base')
        label_features = server.rtr(f'{PLUGIN_ID}.status.features')
        src.reply(RTextList(
            RText(server.rtr(f'{PLUGIN_ID}.status.title') + '\n', styles=RStyle.bold),
            server.rtr(f'{PLUGIN_ID}.status.line', label_base, base),
            server.rtr(f'{PLUGIN_ID}.status.line', label_features, features),
        ))

    def cmd_reload(src):
        c = _get_config(server)
        if not src.has_permission(c.admin_permission):
            src.reply(server.rtr(f'{PLUGIN_ID}.permission_denied'))
            return
        server.reload_plugin(PLUGIN_ID)

    server.register_command(
        Literal(prefix).runs(cmd_status).then(
            Literal('reload').requires(
                lambda src: src.has_permission(cfg.admin_permission),
                failure_message_getter=lambda: server.rtr(f'{PLUGIN_ID}.permission_denied'),
            ).runs(cmd_reload)
        ).then(
            Literal('status').runs(cmd_status)
        )
    )
    server.register_help_message(prefix, server.rtr(f'{PLUGIN_ID}.help.unified_handler'))
