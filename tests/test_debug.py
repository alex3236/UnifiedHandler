"""Tests for debug mode and lifecycle tracking."""
import unittest
import re

from mcdreforged.handler.impl.basic_handler import BasicHandler
from mcdreforged.handler.impl.vanilla_handler import VanillaHandler
from mcdreforged.info_reactor.info import Info, InfoSource

from .common import load_profile, make_handler, parse_line
from unified_handler.profile_loader import compile_features, CompiledProfile
from unified_handler.handler import UnifiedHandler


class _MockLogger:
    def __init__(self):
        self.messages = []

    def info(self, msg):
        self.messages.append(msg)


class TestDebugLog(unittest.TestCase):
    """_debug_log behaviour."""

    def setUp(self):
        self.logger = _MockLogger()
        profile = load_profile('commandblock')
        self.handler = make_handler(profile, VanillaHandler(), mode='wrapper')
        self.handler._logger = self.logger

    def test_no_output_when_debug_off(self):
        self.handler.set_debug(False)
        self.handler._debug_log('should not appear')
        self.assertEqual([], self.logger.messages)

    def test_output_when_debug_on(self):
        self.handler.set_debug(True)
        self.handler._debug_log('hello debug')
        self.assertEqual(1, len(self.logger.messages))
        self.assertIn('hello debug', self.logger.messages[0])

    def test_no_crash_when_logger_is_none(self):
        self.handler._logger = None
        self.handler.set_debug(True)
        self.handler._debug_log('should not crash')

    def test_set_debug_toggles_state(self):
        self.handler.set_debug(False)
        self.assertFalse(self.handler._debug)
        self.handler.set_debug(True)
        self.assertTrue(self.handler._debug)

    def test_set_debug_resets_miss_counter(self):
        self.handler._log_format_miss_count = 42
        self.handler.set_debug(True)
        self.assertEqual(0, self.handler._log_format_miss_count)


class TestLifecycleTracking(unittest.TestCase):
    """Lifecycle flags set correctly when handler methods detect events."""

    def setUp(self):
        cb = load_profile('commandblock')
        compiled = compile_features([cb])
        self.handler = UnifiedHandler(VanillaHandler(), compiled, mode='wrapper')

    def _info(self, content):
        return parse_line(
            self.handler,
            '[09:00:00] [Server thread/INFO]: ' + content
        )

    def test_version_detected_via_base(self):
        info = self._info('Starting minecraft server version 1.21.8')
        result = self.handler.parse_server_version(info)
        self.assertEqual('1.21.8', result)
        self.assertTrue(self.handler._detected_version)

    def test_startup_detected_via_base(self):
        info = self._info('Done (12.080s)! For help, type "help"')
        result = self.handler.test_server_startup_done(info)
        self.assertTrue(result)
        self.assertTrue(self.handler._detected_startup)

    def test_rcon_detected_via_base(self):
        info = self._info('RCON running on 0.0.0.0:25575')
        result = self.handler.test_rcon_started(info)
        self.assertTrue(result)
        self.assertTrue(self.handler._detected_rcon)

    def test_stopping_detected_via_base(self):
        info = self._info('Stopping server')
        result = self.handler.test_server_stopping(info)
        self.assertTrue(result)
        self.assertTrue(self.handler._detected_stopping)

    def test_address_not_detected_initially(self):
        self.assertFalse(self.handler._address_detected)

    def test_version_not_detected_initially(self):
        self.assertFalse(self.handler._detected_version)

    def test_startup_not_detected_initially(self):
        self.assertFalse(self.handler._detected_startup)

    def test_lifecycle_status_format(self):
        self.handler._detected_version = True
        self.handler._detected_startup = True
        self.handler._detected_rcon = True
        self.handler._detected_stopping = True
        self.handler._address_detected = True
        self.handler._c.stop_command = 'stop'

        lines = self.handler.get_lifecycle_status()
        text = '\n'.join(lines)

        self.assertIn('=== Lifecycle Status ===', text)
        self.assertIn('server_version:', text)
        self.assertIn('server_address:', text)
        self.assertIn('startup_done:', text)
        self.assertIn('rcon_started:', text)
        self.assertIn('server_stopping:', text)
        self.assertIn('stop_command:', text)
        # 2 fences + 5 standard + 1 stop_command = 8
        self.assertEqual(8, len(lines))

    def test_lifecycle_status_when_nothing_detected(self):
        lines = self.handler.get_lifecycle_status()
        text = '\n'.join(lines)
        self.assertNotIn('send_msg', text)
        self.assertNotIn('broadcast', text)


class TestApplyPlayerPatternsReturn(unittest.TestCase):
    """_apply_player_patterns returns bool."""

    def setUp(self):
        cp = load_profile('chat_prefixes')
        compiled = compile_features([cp])
        self.handler = UnifiedHandler(VanillaHandler(), compiled, mode='wrapper')

    def test_returns_true_when_pattern_matches(self):
        info = parse_line(
            self.handler,
            '[09:00:00] [Server thread/INFO]: <[Red]Steve> hello'
        )
        # parse_line already ran _apply_player_patterns which
        # matched and overwrote info.content to just "hello".
        # Reset to the parsed content to test the method in isolation.
        info.player = None
        info.content = '<[Red]Steve> hello'
        result = self.handler._apply_player_patterns(info)
        self.assertTrue(result)
        self.assertEqual('Steve', info.player)

    def test_returns_false_when_player_already_set(self):
        info = parse_line(
            self.handler,
            '[09:00:00] [Server thread/INFO]: <Steve> hello'
        )
        # Base handler set player; _apply_player_patterns should skip
        result = self.handler._apply_player_patterns(info)
        self.assertFalse(result)

    def test_returns_false_when_no_pattern_matches(self):
        info = parse_line(
            self.handler,
            '[09:00:00] [Server thread/INFO]: RCON running on 0.0.0.0:25575'
        )
        info.player = None
        result = self.handler._apply_player_patterns(info)
        self.assertFalse(result)
        self.assertIsNone(info.player)


class TestAttachExtraFields(unittest.TestCase):
    """_attach_extra_fields works as instance method."""

    def test_attaches_field_to_info(self):
        handler = UnifiedHandler(BasicHandler(), CompiledProfile(), mode='full_profile')
        info = Info(InfoSource.SERVER, '')
        handler._attach_extra_fields(info, {'subserver': 'hub'}, {'subserver': 'subserver'})
        self.assertEqual('hub', info.subserver)

    def test_noop_when_group_not_present(self):
        handler = UnifiedHandler(BasicHandler(), CompiledProfile(), mode='full_profile')
        info = Info(InfoSource.SERVER, '')
        handler._attach_extra_fields(info, {'other': 'x'}, {'subserver': 'subserver'})
        self.assertFalse(hasattr(info, 'subserver'))


class TestDebugPlayerSourceTracking(unittest.TestCase):
    """_debug_player_source tracks which layer identified the player."""

    def setUp(self):
        self.handler = UnifiedHandler(VanillaHandler(), CompiledProfile(), mode='wrapper')

    def test_reset_before_parsing(self):
        info = parse_line(
            self.handler,
            '[09:00:00] [Server thread/INFO]: <Steve> hello'
        )
        self.assertEqual('base', self.handler._debug_player_source)

    def test_profile_wins_over_base(self):
        cp = load_profile('chat_prefixes')
        compiled = compile_features([cp])
        handler = UnifiedHandler(VanillaHandler(), compiled, mode='wrapper',
                                 debug=True)
        info = parse_line(
            handler,
            '[09:00:00] [Server thread/INFO]: <[Red]Steve> hello'
        )
        self.assertEqual('profile', handler._debug_player_source)

    def test_pseudo_player_source(self):
        cp = load_profile('commandblock')
        compiled = compile_features([cp])
        handler = UnifiedHandler(VanillaHandler(), compiled, mode='wrapper',
                                 debug=True)
        info = parse_line(
            handler,
            '[09:00:00] [Server thread/INFO]: [@] time set day'
        )
        self.assertEqual('pseudo', handler._debug_player_source)
