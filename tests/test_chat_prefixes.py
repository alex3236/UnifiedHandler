"""Tests for chat_prefixes feature profile.

Original: TitlePrefixHandler (38 lines) + VanillaTeamHandler (35 lines),
both extending VanillaHandler. Merged into chat_prefixes.
"""
import unittest

from mcdreforged.handler.impl.forge_handler import ForgeHandler
from mcdreforged.handler.impl.vanilla_handler import VanillaHandler

from .common import load_profile, make_handler, parse_line


class TestChatPrefixesProfile(unittest.TestCase):
    def setUp(self):
        profile = load_profile('chat_prefixes')
        self.handler = make_handler(profile, VanillaHandler())

    # ── TitlePrefix: bracket group stripping ──

    def test_title_prefix_stripped(self):
        """Three bracket groups stripped, player detected."""
        info = parse_line(
            self.handler,
            '[09:00:00] [Server thread/INFO]: '
            '[Rcon][Owner][Admin] <Fallen_Breath> hello'
        )
        self.assertEqual('Fallen_Breath', info.player)
        self.assertEqual('hello', info.content)

    def test_title_prefix_double_bracket_only(self):
        """Two bracket groups: both stripped, player still detected."""
        info = parse_line(
            self.handler,
            '[09:00:00] [Server thread/INFO]: '
            '[Rcon][Owner] <Fallen_Breath> hello'
        )
        self.assertEqual('Fallen_Breath', info.player)
        self.assertEqual('hello', info.content)

    def test_title_prefix_single_bracket(self):
        """Edge: exactly one title bracket group — stripped, player detected."""
        info = parse_line(
            self.handler,
            '[09:00:00] [Server thread/INFO]: '
            '[Admin] <Fallen_Breath> hello'
        )
        self.assertEqual('Fallen_Breath', info.player)
        self.assertEqual('hello', info.content)

    def test_title_prefix_with_forge_format(self):
        """Title prefixes on a Forge log format line."""
        profile = load_profile('chat_prefixes')
        handler = make_handler(profile, ForgeHandler())
        info = parse_line(
            handler,
            '[00:55:36] [Server thread/INFO] [minecraft/DedicatedServer]: '
            '[Rcon][Owner][Admin] <Steve> hello forge'
        )
        self.assertEqual('Steve', info.player)
        self.assertEqual('hello forge', info.content)

    # ── VanillaTeam: <[Team]Name> parsing ──

    def test_team_prefix_player_message(self):
        info = parse_line(
            self.handler,
            '[09:00:00] [Server thread/INFO]: '
            '<[TeamRed]Fallen_Breath> hi team'
        )
        self.assertEqual('Fallen_Breath', info.player)
        self.assertEqual('hi team', info.content)

    def test_team_prefix_not_secure(self):
        info = parse_line(
            self.handler,
            '[09:00:00] [Server thread/INFO]: '
            '[Not Secure] <[Blue]Steve> hello'
        )
        self.assertEqual('Steve', info.player)
        self.assertEqual('hello', info.content)

    def test_team_prefix_works_with_forge(self):
        profile = load_profile('chat_prefixes')
        handler = make_handler(profile, ForgeHandler())
        info = parse_line(
            handler,
            '[00:55:36] [Server thread/INFO] [minecraft/DedicatedServer]: '
            '<[Green]Alex> hi forge'
        )
        self.assertEqual('Alex', info.player)
        self.assertEqual('hi forge', info.content)

    # ── normal player fallthrough ──

    def test_normal_player_still_works(self):
        info = parse_line(
            self.handler,
            '[09:00:00] [Server thread/INFO]: '
            '<Fallen_Breath> normal chat'
        )
        self.assertEqual('Fallen_Breath', info.player)
        self.assertEqual('normal chat', info.content)
