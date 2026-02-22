import sys
import os
import unittest
import json
import base64
from unittest.mock import MagicMock, patch, mock_open

# Add parent directory to path to import core
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.image_service import EndpointImageProvider

class TestEndpointImageProvider(unittest.TestCase):
    def setUp(self):
        self.mock_ctx = MagicMock()
        self.api_config = {"model": "test-model"}
        with patch('core.image_service.LlmClient') as mock_client_cls:
            self.provider = EndpointImageProvider(self.api_config, self.mock_ctx)
            self.mock_client = self.provider.client

    @patch('core.image_service.sync_request')
    def test_generate_openrouter_url(self, mock_sync):
        self.mock_client.config.get.side_effect = lambda k, d=None: True if k == "is_openrouter" else d
        self.mock_client.make_chat_request.return_value = ("POST", "/chat", "{}", {})
        
        # Mock OpenRouter response with image URL
        mock_resp = {
            "content": "Here is your image",
            "images": [{"image_url": {"url": "http://example.com/image.png"}}]
        }
        self.mock_client.request_with_tools.return_value = mock_resp
        mock_sync.return_value = b"fake-image-data"

        result = self.provider.generate("test prompt")
        
        self.assertEqual(len(result), 1)
        self.assertTrue(result[0].endswith(".webp"))
        mock_sync.assert_called_once_with("http://example.com/image.png", parse_json=False)

    def test_generate_openrouter_b64(self):
        self.mock_client.config.get.side_effect = lambda k, d=None: True if k == "is_openrouter" else d
        self.mock_client.make_chat_request.return_value = ("POST", "/chat", "{}", {})
        
        # Mock OpenRouter response with b64 image
        b64_data = base64.b64encode(b"fake-image-data-b64").decode()
        mock_resp = {
            "images": [{"image_url": f"data:image/png;base64,{b64_data}"}]
        }
        self.mock_client.request_with_tools.return_value = mock_resp

        result = self.provider.generate("test prompt")
        
        self.assertEqual(len(result), 1)
        self.assertTrue(result[0].endswith(".png"))
        with open(result[0], 'rb') as f:
            self.assertEqual(f.read(), b"fake-image-data-b64")
        os.unlink(result[0])

    def test_generate_standard_b64(self):
        self.mock_client.config.get.return_value = False # Not OpenRouter
        self.mock_client.make_image_request.return_value = ("POST", "/images", "{}", {})
        
        # Mock standard connection and response
        mock_conn = MagicMock()
        self.mock_client._get_connection.return_value = mock_conn
        mock_http_resp = MagicMock()
        mock_http_resp.status = 200
        b64_data = base64.b64encode(b"standard-b64-data").decode()
        resp_data = {"data": [{"b64_json": b64_data}]}
        mock_http_resp.read.return_value = json.dumps(resp_data).encode()
        mock_conn.getresponse.return_value = mock_http_resp

        result = self.provider.generate("test prompt")
        
        self.assertEqual(len(result), 1)
        self.assertTrue(result[0].endswith(".png"))
        with open(result[0], 'rb') as f:
            self.assertEqual(f.read(), b"standard-b64-data")
        os.unlink(result[0])

    @patch('core.image_service.sync_request')
    def test_fallback_logic_url(self, mock_sync):
        self.mock_client.config.get.side_effect = lambda k, d=None: True if k == "is_openrouter" else d
        self.mock_client.make_chat_request.return_value = ("POST", "/chat", "{}", {})
        
        # Mock response where image is in content (fallback)
        mock_resp = {
            "content": "http://fallback.com/image.png",
            "images": []
        }
        self.mock_client.request_with_tools.return_value = mock_resp
        mock_sync.return_value = b"fallback-image-data"

        result = self.provider.generate("test prompt")
        
        self.assertEqual(len(result), 1)
        mock_sync.assert_called_with("http://fallback.com/image.png", parse_json=False)
        os.unlink(result[0])

    def test_fallback_logic_b64(self):
        self.mock_client.config.get.side_effect = lambda k, d=None: True if k == "is_openrouter" else d
        self.mock_client.make_chat_request.return_value = ("POST", "/chat", "{}", {})
        
        # Mock response where image is in content (fallback b64)
        b64_data = base64.b64encode(b"fallback-b64-data").decode()
        mock_resp = {
            "content": f"Check this out: data:image/png;base64,{b64_data}",
            "images": []
        }
        self.mock_client.request_with_tools.return_value = mock_resp

        result = self.provider.generate("test prompt")
        
        self.assertEqual(len(result), 1)
        with open(result[0], 'rb') as f:
            self.assertEqual(f.read(), b"fallback-b64-data")
        os.unlink(result[0])

    def test_scoping_bug_fix_verification(self):
        """
        Verifies that the scoping bug is fixed. 
        Previously, 'response' in the fallback block would be an HTTPResponse 
        if the standard path was taken, causing a crash.
        """
        self.mock_client.config.get.return_value = False # Standard path
        self.mock_client.make_image_request.return_value = ("POST", "/images", "{}", {})
        
        # Mock standard connection and response that returns no images in data
        mock_conn = MagicMock()
        self.mock_client._get_connection.return_value = mock_conn
        mock_http_resp = MagicMock()
        mock_http_resp.status = 200
        resp_data = {"data": []} # No images
        mock_http_resp.read.return_value = json.dumps(resp_data).encode()
        mock_conn.getresponse.return_value = mock_http_resp

        # This should NOT crash now, even if fallback fails to find anything.
        # It should just return [].
        try:
            result = self.provider.generate("test prompt")
            self.assertEqual(result, [])
        except AttributeError as e:
            self.fail(f"Scoping bug still present! AttributeError: {e}")

if __name__ == '__main__':
    unittest.main()
