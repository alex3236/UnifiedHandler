from typing import List, Optional
from mcdreforged.api.all import Serializable


class PluginConfig(Serializable):
    # 服务端适配 — 多选一
    # "auto" = 从 MCDR 配置自动检测
    # "vanilla_handler" / "forge_handler" / ... = MCDR 内置 handler 名称
    # "mypackage.MyHandler" = 完整 Python 类路径
    # "bedrock_bds" = 使用内置的 base profile
    base_handler: str = "auto"

    # 功能增强 — 可多选，按顺序叠加
    features: List[str] = []

    # 命令前缀（用于插件的 MCDR 命令）
    command_prefix: str = "!!uh"

    # 管理命令所需的最低权限等级
    admin_permission: int = 3
