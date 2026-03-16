import sys
import os
import json
import tempfile
import unittest
from unittest.mock import MagicMock, patch

# Mock uno and unohelper
sys.modules['uno'] = MagicMock()
mock_unohelper = MagicMock()
class MockUnoBase: pass
mock_unohelper.Base = MockUnoBase
sys.modules['unohelper'] = mock_unohelper

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from plugin.framework.config import (
    get_image_model, set_image_model, get_api_key_for_endpoint, set_api_key_for_endpoint,
    add_config_listener, notify_config_changed, _config_listeners
)

class TestConfigSync(unittest.TestCase):
    def setUp(self):
        self.ctx = MagicMock()
        self.config_data = {}
        
        # Mock get_config and set_config (get_config no longer takes default; mock supplies "" when missing)
        def mock_get_config(ctx, key):
            return self.config_data.get(key, "")
        
        def mock_set_config(ctx, key, value):
            self.config_data[key] = value
            
        self.get_patcher = patch('plugin.framework.config.get_config', side_effect=mock_get_config)
        self.set_patcher = patch('plugin.framework.config.set_config', side_effect=mock_set_config)
        self.notify_patcher = patch('plugin.framework.config.notify_config_changed')
        
        self.mock_get = self.get_patcher.start()
        self.mock_set = self.set_patcher.start()
        self.mock_notify = self.notify_patcher.start()

    def tearDown(self):
        self.get_patcher.stop()
        self.set_patcher.stop()
        self.notify_patcher.stop()

    def test_set_image_model_aihorde(self):
        self.config_data["image_provider"] = "aihorde"
        set_image_model(self.ctx, "new-horde-model")
        
        self.assertEqual(self.config_data.get("aihorde_model"), "new-horde-model")
        self.assertIsNone(self.config_data.get("image_model"))
        self.mock_notify.assert_called_once_with(self.ctx)

    def test_set_image_model_endpoint(self):
        self.config_data["image_provider"] = "endpoint"
        with patch('plugin.framework.config.update_lru_history') as mock_lru:
            set_image_model(self.ctx, "new-endpoint-model")
            
            self.assertEqual(self.config_data.get("image_model"), "new-endpoint-model")
            self.assertIsNone(self.config_data.get("aihorde_model"))
            mock_lru.assert_called_once_with(self.ctx, "new-endpoint-model", "image_model_lru", "")
            self.mock_notify.assert_called_once_with(self.ctx)

    def test_get_image_model(self):
        # Test AI Horde
        self.config_data["image_provider"] = "aihorde"
        self.config_data["aihorde_model"] = "horde-1"
        self.assertEqual(get_image_model(self.ctx), "horde-1")
        
        # Test Endpoint
        self.config_data["image_provider"] = "endpoint"
        self.config_data["image_model"] = "end-1"
        self.assertEqual(get_image_model(self.ctx), "end-1")

    def test_get_api_key_for_endpoint_missing(self):
        self.assertEqual(get_api_key_for_endpoint(self.ctx, "http://localhost:11434"), "")

    def test_get_api_key_for_endpoint_existing(self):
        self.config_data["api_keys_by_endpoint"] = {"http://localhost:11434": "test-key-123"}
        self.assertEqual(get_api_key_for_endpoint(self.ctx, "http://localhost:11434"), "test-key-123")

        # Test endpoint normalization
        self.assertEqual(get_api_key_for_endpoint(self.ctx, "http://localhost:11434/"), "test-key-123")

    def test_set_api_key_for_endpoint(self):
        # Starts empty
        set_api_key_for_endpoint(self.ctx, "http://localhost:11434", "new-key")
        self.assertEqual(self.config_data.get("api_keys_by_endpoint", {}).get("http://localhost:11434"), "new-key")

        # Updates existing, normalizes endpoint
        set_api_key_for_endpoint(self.ctx, "http://localhost:11434/", "updated-key")
        self.assertEqual(self.config_data.get("api_keys_by_endpoint", {}).get("http://localhost:11434"), "updated-key")

    def test_add_config_listener_and_notify(self):
        # Temporarily clear listeners to isolate the test
        original_listeners = list(_config_listeners)
        _config_listeners.clear()
        try:
            called = []
            def my_callback(ctx):
                called.append(ctx)

            add_config_listener(my_callback)

            # Since notify_config_changed is mocked in setUp, we need to temporarily stop the patch
            # to test its actual implementation
            self.notify_patcher.stop()
            try:
                notify_config_changed(self.ctx)
                self.assertEqual(len(called), 1)
                self.assertEqual(called[0], self.ctx)

                # Test exception swallowing
                def bad_callback(ctx):
                    raise ValueError("Simulated error")
                add_config_listener(bad_callback)

                notify_config_changed(self.ctx)
                self.assertEqual(len(called), 2) # First callback still gets called again
            finally:
                self.mock_notify = self.notify_patcher.start()
        finally:
            _config_listeners.clear()
            _config_listeners.extend(original_listeners)


class TestConfigSyncFileIO(unittest.TestCase):
    def setUp(self):
        self.ctx = MagicMock()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.config_path = os.path.join(self.temp_dir.name, "writeragent.json")

        def mock_config_path(ctx):
            return self.config_path

        self.path_patcher = patch('plugin.framework.config._config_path', side_effect=mock_config_path)
        self.path_patcher.start()

    def tearDown(self):
        self.path_patcher.stop()
        self.temp_dir.cleanup()

    def test_set_api_key_file_io(self):
        # Ensure file is written correctly
        set_api_key_for_endpoint(self.ctx, "http://api.openai.com", "sk-1234")

        self.assertTrue(os.path.exists(self.config_path))
        with open(self.config_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.assertIn("api_keys_by_endpoint", data)
        self.assertEqual(data["api_keys_by_endpoint"].get("http://api.openai.com"), "sk-1234")

        # Ensure we can read it back via actual config functions
        self.assertEqual(get_api_key_for_endpoint(self.ctx, "http://api.openai.com"), "sk-1234")

    def test_get_api_key_file_io_missing_file(self):
        # Should handle missing file gracefully
        self.assertEqual(get_api_key_for_endpoint(self.ctx, "http://api.openai.com"), "")


if __name__ == '__main__':
    unittest.main()
