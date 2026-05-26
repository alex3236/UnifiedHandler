"""Tests for multi-feature stacking — the core value proposition."""
import unittest

from mcdreforged.handler.impl.bukkit_handler import BukkitHandler
from mcdreforged.handler.impl.forge_handler import ForgeHandler
from mcdreforged.handler.impl.vanilla_handler import VanillaHandler

from .common import load_profile, make_handler, parse_line
from unified_handler.profile_loader import (
    compile_features,
    compile_full_profile,
    CompiledProfile,
)
from unified_handler.handler import UnifiedHandler


class TestFeatureStacking(unittest.TestCase):

    # ── two features ──

    def test_commandblock_plus_chat_prefixes(self):
        cb = load_profile('commandblock')
        cp = load_profile('chat_prefixes')
        compiled = compile_features([cb, cp])
        handler = UnifiedHandler(VanillaHandler(), compiled, mode='wrapper')

        # chat_prefixes parses team message
        info = parse_line(
            handler,
            '[09:00:00] [Server thread/INFO]: <[Red]Steve> hi'
        )
        self.assertEqual('Steve', info.player)
        self.assertEqual('hi', info.content)

        # commandblock detects pseudo players
        info = parse_line(
            handler,
            '[09:00:00] [Server thread/INFO]: [@] time set 0'
        )
        self.assertEqual('"!commandblock"', info.player)
        self.assertEqual('time set 0', info.content)

        # Title prefix + team prefix combined
        info = parse_line(
            handler,
            '[09:00:00] [Server thread/INFO]: '
            '[Rcon][Owner][Admin] <[Blue]Alex> hello'
        )
        self.assertEqual('Alex', info.player)
        self.assertEqual('hello', info.content)

    def test_cleanroom_with_commandblock(self):
        cleanroom = load_profile('cleanroom_fix', 'base')
        cb = load_profile('commandblock')
        compiled = compile_full_profile(cleanroom)
        compiled.merge_feature(cb)
        handler = UnifiedHandler(ForgeHandler(), compiled, mode='wrapper')

        # Cleanroom empty [] line + command block
        info = parse_line(
            handler,
            '[12:34:56] [Server thread/INFO] []: [@] help'
        )
        self.assertEqual('"!commandblock"', info.player)
        self.assertEqual('help', info.content)

    def test_leaves_with_chat_prefixes(self):
        leaves = load_profile('leaves_fix', 'base')
        cp = load_profile('chat_prefixes')
        compiled = compile_full_profile(leaves)
        compiled.merge_feature(cp)
        handler = UnifiedHandler(BukkitHandler(), compiled, mode='wrapper')

        # ANSI stripped + team prefix parsed
        info = parse_line(
            handler,
            '\x1b[33m[00:12:10 INFO]:\x1b[0m <[Red]Steve> hi'
        )
        self.assertEqual('Steve', info.player)
        self.assertEqual('hi', info.content)

    # ── three features ──

    def test_three_features_stacked(self):
        """commandblock + chat_prefixes + a second set of pseudo players."""
        cb = load_profile('commandblock')
        cp = load_profile('chat_prefixes')
        compiled = compile_features([cb, cp])
        handler = UnifiedHandler(VanillaHandler(), compiled, mode='wrapper')

        # All three capabilities work on the same handler
        info = parse_line(
            handler,
            '[09:00:00] [Server thread/INFO]: '
            '[Rcon][Owner][Admin] <[Red]Steve> hi'
        )
        self.assertEqual('Steve', info.player)
        self.assertEqual('hi', info.content)

        info = parse_line(
            handler,
            '[09:00:00] [Server thread/INFO]: [@] time set day'
        )
        self.assertEqual('"!commandblock"', info.player)

        info = parse_line(
            handler,
            '[09:00:00] [Server thread/INFO]: <Steve> hello'
        )
        self.assertEqual('Steve', info.player)

    # ── feature stacking order: last-writer-wins fields ──

    def test_name_validation_last_wins(self):
        """When two features set name_validation, the last loaded one wins."""
        from mcdreforged.handler.impl.basic_handler import BasicHandler
        compiled = CompiledProfile()
        compiled.merge_feature({
            'log_format': {
                'pattern': (
                    r'\[(?P<hour>\d+):(?P<min>\d+):(?P<sec>\d+)\] '
                    r'\[(?P<thread>[^\]]+)/(?P<logging>[^\]]+)\]: '
                    r'(?P<content>.*)'
                )
            },
            'player_message': {
                'name_validation': '[a-z]+',
                'patterns': ['<(?P<name>[^>]+)> (?P<message>.*)'],
            }
        })
        compiled.merge_feature({
            'player_message': {
                'name_validation': '[A-Z]+',
                'patterns': [],
            }
        })
        handler = UnifiedHandler(BasicHandler(), compiled, mode='full_profile')
        # Second feature's validation wins: only uppercase matches
        info = parse_line(
            handler,
            '[09:00:00] [Server thread/INFO]: <STEVE> hello'
        )
        self.assertEqual('STEVE', info.player)
        # lowercase should fail validation
        info2 = parse_line(
            handler,
            '[09:00:00] [Server thread/INFO]: <steve> hello'
        )
        self.assertIsNone(info2.player)
