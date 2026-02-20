
import sys
import os
import unittest
from unittest.mock import MagicMock, patch

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.image_service import ImageService, AIHordeImageProvider

class TestImageStatusCallback(unittest.TestCase):
    def test_status_callback_propagation(self):
        # Mock context and config
        mock_ctx = MagicMock()
        mock_ctx.ServiceManager.createInstanceWithContext.return_value = MagicMock() # Toolkit
        
        config = {"aihorde_api_key": "test_key", "image_provider": "aihorde"}
        
        # Instantiate ImageService
        service = ImageService(mock_ctx, config)
        
        # Mock the callback
        status_callback = MagicMock()
        
        # Verify provider creation
        provider = service.get_provider("aihorde")
        self.assertIsInstance(provider, AIHordeImageProvider)
        
        # Verify SimpleInformer setup
        informer = provider.client.informer
        self.assertIsNotNone(informer)
        
        # Simulate generate call
        # Mock AiHordeClient.generate_image to call informer.update_status
        def mock_generate_image(options):
            # Simulate progress
            informer.update_status("Starting...", 0)
            informer.update_status("Generating...", 50)
            return ["/tmp/image.png"]
            
        with patch.object(service, 'get_provider', return_value=provider):
            with patch.object(provider.client, 'generate_image', side_effect=mock_generate_image):
                result = service.generate_image("test prompt", status_callback=status_callback)
                
                # Assert calls
                self.assertEqual(result, ["/tmp/image.png"])
                
                # Check callback calls
                # Use assert_has_calls to verify sequence
                from unittest.mock import call
                expected_calls = [
                    call("Horde: Starting... (0%)"),
                    call("Horde: Generating... (50%)")
                ]
                status_callback.assert_has_calls(expected_calls)
                print("Status callback successfully invoked!")

if __name__ == '__main__':
    unittest.main()
