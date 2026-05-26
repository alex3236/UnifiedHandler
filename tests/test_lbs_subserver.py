"""Tests for lbs_subserver base profile.

Original: LBSVelocityHandler (89 lines, extends VelocityHandler, 8 overrides).
"""
import unittest

from mcdreforged.handler.impl.velocity_handler import VelocityHandler

from .common import load_profile, parse_line
from unified_handler.profile_loader import compile_full_profile
from unified_handler.handler import UnifiedHandler


VELOCITY_LIFECYCLE = r'''
[00:23:38 INFO]: Booting up Velocity 3.0.0...
[00:23:39 INFO] [viaversion]: ViaVersion detected lowest supported version by the proxy: 1.7-1.7.5 (4)
[00:23:40 INFO]: Listening on /[0:0:0:0:0:0:0:0]:25577
[00:23:40 INFO]: Done (3.17s)!
[00:23:45 INFO]: [connected player] Fallen_Breath (/127.0.0.1:13580) has connected
[00:16:35 INFO] [/survival]: <Fallen_Breath> hello proxy
[00:16:36 INFO] [/factions]: <Fallen_Breath> !!MCDR help
[00:23:52 INFO]: [connected player] Fallen_Breath (/127.0.0.1:13580) has disconnected
[00:23:52 INFO]: Shutting down the proxy...
'''.strip()


class TestLBSSubserverProfile(unittest.TestCase):
    def setUp(self):
        profile = load_profile('lbs_subserver', 'base')
        compiled = compile_full_profile(profile)
        self.handler = UnifiedHandler(
            VelocityHandler(), compiled, mode='wrapper'
        )

    # ── subserver player message ──

    def test_subserver_player_message(self):
        info = parse_line(
            self.handler,
            '[00:16:35 INFO] [/survival]: <Fallen_Breath> hello'
        )
        self.assertEqual('Fallen_Breath', info.player)
        self.assertEqual('hello', info.content)

    def test_subserver_injected_to_info(self):
        """The /survival subserver name is attached to Info."""
        info = parse_line(
            self.handler,
            '[00:16:35 INFO] [/factions]: <Steve> raid incoming'
        )
        self.assertEqual('Steve', info.player)
        self.assertEqual('raid incoming', info.content)
        self.assertEqual('/factions', getattr(info, 'subserver', None))

    # ── command prefix routing ──

    def test_prefix_routing_vmcdr_to_mcdr(self):
        """!!VMCDR is replaced with !!MCDR."""
        info = parse_line(
            self.handler,
            '[00:16:35 INFO] [/survival]: '
            '<Fallen_Breath> !!VMCDR plg reload foo'
        )
        self.assertEqual('Fallen_Breath', info.player)
        self.assertEqual('!!MCDR plg reload foo', info.content)

    def test_prefix_routing_mcdr_to_vmcdr(self):
        """Reverse: !!MCDR is replaced with !!VMCDR."""
        info = parse_line(
            self.handler,
            '[00:16:36 INFO] [/factions]: '
            '<Fallen_Breath> !!MCDR help'
        )
        self.assertEqual('Fallen_Breath', info.player)
        self.assertEqual('!!VMCDR help', info.content)

    def test_stop_on_match_prevents_ping_pong(self):
        """Without stop_on_match the two rules would undo each other.
        !!VMCDR → !!MCDR (stop) — never reaches the !!MCDR → !!VMCDR rule."""
        info = parse_line(
            self.handler,
            '[00:16:35 INFO] [/survival]: '
            '<Fallen_Breath> !!VMCDR status'
        )
        self.assertEqual('!!MCDR status', info.content)

    # ── velocity base handler delegation ──

    def test_velocity_join_still_detected(self):
        info = parse_line(
            self.handler,
            '[00:19:07 INFO]: [connected player] Fallen_Breath '
            '(/127.0.0.1:13394) has connected'
        )
        self.assertEqual('Fallen_Breath',
                         self.handler.parse_player_joined(info))

    def test_velocity_left_still_detected(self):
        info = parse_line(
            self.handler,
            '[00:20:32 INFO]: [connected player] TestName '
            '(/127.0.0.1:13456) has disconnected'
        )
        self.assertEqual('TestName',
                         self.handler.parse_player_left(info))

    def test_velocity_startup_detected(self):
        info = parse_line(
            self.handler,
            '[00:19:04 INFO]: Done (3.11s)!'
        )
        self.assertTrue(self.handler.test_server_startup_done(info))

    def test_velocity_stopping_detected(self):
        info = parse_line(
            self.handler,
            '[00:21:40 INFO]: Shutting down the proxy...'
        )
        self.assertTrue(self.handler.test_server_stopping(info))

    def test_velocity_server_address(self):
        info = parse_line(
            self.handler,
            '[00:23:40 INFO]: Listening on /[0:0:0:0:0:0:0:0]:25577'
        )
        self.assertEqual(
            ('[0:0:0:0:0:0:0:0]', 25577),
            self.handler.parse_server_address(info)
        )

    # ── commands ──

    def test_send_message_uses_alertraw(self):
        cmd = self.handler.get_send_message_command(
            'Fallen_Breath', 'Hello', None)
        self.assertIsNotNone(cmd)
        self.assertIn('alertraw', cmd)
        self.assertIn('Fallen_Breath', cmd)
        self.assertIn('Hello', cmd)

    def test_broadcast_uses_alertraw(self):
        cmd = self.handler.get_broadcast_message_command('Hello', None)
        self.assertIsNotNone(cmd)
        self.assertIn('alertraw', cmd)
        self.assertIn('@a', cmd)
        self.assertIn('Hello', cmd)

    # ── full lifecycle ──

    def test_velocity_lifecycle(self):
        for line in VELOCITY_LIFECYCLE.splitlines():
            info = parse_line(self.handler, line)
            self.assertIsNotNone(info)
