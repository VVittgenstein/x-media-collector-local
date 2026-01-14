"""
Tests for src/backend/net/proxy.py

Covers:
- ProxyConfig validation
- Proxy URL handling
- urllib proxy handler generation
"""

import unittest

from src.backend.net.proxy import ProxyConfig, get_urllib_proxy_handlers


class TestProxyConfig(unittest.TestCase):
    """Tests for ProxyConfig."""

    def test_default_disabled(self):
        """Proxy is disabled by default."""
        config = ProxyConfig()
        self.assertFalse(config.enabled)
        self.assertEqual(config.url, "")
        self.assertFalse(config.is_active())
        self.assertIsNone(config.get_url())

    def test_enabled_with_url(self):
        """Enabled proxy with URL should be active."""
        config = ProxyConfig(enabled=True, url="http://proxy:8080")
        self.assertTrue(config.is_active())
        self.assertEqual(config.get_url(), "http://proxy:8080")

    def test_enabled_without_url_not_active(self):
        """Enabled proxy without URL should not be active."""
        config = ProxyConfig(enabled=True, url="")
        self.assertFalse(config.is_active())
        self.assertIsNone(config.get_url())

    def test_disabled_with_url_not_active(self):
        """Disabled proxy with URL should not be active."""
        config = ProxyConfig(enabled=False, url="http://proxy:8080")
        self.assertFalse(config.is_active())
        self.assertIsNone(config.get_url())

    def test_url_stripped(self):
        """URL should be stripped of whitespace."""
        config = ProxyConfig(enabled=True, url="  http://proxy:8080  ")
        self.assertEqual(config.get_url(), "http://proxy:8080")

    def test_to_persist_dict(self):
        """Config can be serialized."""
        config = ProxyConfig(enabled=True, url="socks5://proxy:1080")
        data = config.to_persist_dict()
        self.assertTrue(data["enabled"])
        self.assertEqual(data["url"], "socks5://proxy:1080")

    def test_from_persist_dict(self):
        """Config can be deserialized."""
        data = {"enabled": True, "url": "http://user:pass@proxy:8080"}
        config = ProxyConfig.from_persist_dict(data)
        self.assertTrue(config.enabled)
        self.assertEqual(config.url, "http://user:pass@proxy:8080")

    def test_from_persist_dict_missing_fields(self):
        """Missing fields should use defaults."""
        config = ProxyConfig.from_persist_dict({})
        self.assertFalse(config.enabled)
        self.assertEqual(config.url, "")


class TestProxyConfigValidation(unittest.TestCase):
    """Tests for ProxyConfig.validate() method."""

    def test_disabled_always_valid(self):
        """Disabled proxy is always valid."""
        config = ProxyConfig(enabled=False, url="")
        is_valid, error = config.validate()
        self.assertTrue(is_valid)
        self.assertEqual(error, "")

    def test_enabled_empty_url_invalid(self):
        """Enabled proxy with empty URL is invalid."""
        config = ProxyConfig(enabled=True, url="")
        is_valid, error = config.validate()
        self.assertFalse(is_valid)
        self.assertIn("empty", error.lower())

    def test_valid_http_proxy(self):
        """HTTP proxy should be valid."""
        config = ProxyConfig(enabled=True, url="http://proxy:8080")
        is_valid, error = config.validate()
        self.assertTrue(is_valid)
        self.assertEqual(error, "")

    def test_valid_https_proxy(self):
        """HTTPS proxy should be valid."""
        config = ProxyConfig(enabled=True, url="https://proxy:8443")
        is_valid, error = config.validate()
        self.assertTrue(is_valid)

    def test_valid_socks5_proxy(self):
        """SOCKS5 proxy should be valid."""
        config = ProxyConfig(enabled=True, url="socks5://proxy:1080")
        is_valid, error = config.validate()
        self.assertTrue(is_valid)

    def test_valid_socks4_proxy(self):
        """SOCKS4 proxy should be valid."""
        config = ProxyConfig(enabled=True, url="socks4://proxy:1080")
        is_valid, error = config.validate()
        self.assertTrue(is_valid)

    def test_invalid_scheme(self):
        """Unsupported scheme should be invalid."""
        config = ProxyConfig(enabled=True, url="ftp://proxy:21")
        is_valid, error = config.validate()
        self.assertFalse(is_valid)
        self.assertIn("scheme", error.lower())

    def test_missing_scheme(self):
        """URL without scheme should be invalid."""
        config = ProxyConfig(enabled=True, url="proxy:8080")
        is_valid, error = config.validate()
        self.assertFalse(is_valid)
        self.assertIn("scheme", error.lower())

    def test_missing_host(self):
        """URL without host should be invalid."""
        config = ProxyConfig(enabled=True, url="http://")
        is_valid, error = config.validate()
        self.assertFalse(is_valid)
        self.assertIn("host", error.lower())


class TestGetUrllibProxyHandlers(unittest.TestCase):
    """Tests for get_urllib_proxy_handlers function."""

    def test_none_config_returns_empty(self):
        """None config should return empty dict."""
        handlers = get_urllib_proxy_handlers(None)
        self.assertEqual(handlers, {})

    def test_disabled_config_returns_empty(self):
        """Disabled config should return empty dict."""
        config = ProxyConfig(enabled=False, url="http://proxy:8080")
        handlers = get_urllib_proxy_handlers(config)
        self.assertEqual(handlers, {})

    def test_active_config_returns_handlers(self):
        """Active config should return proxy handlers."""
        config = ProxyConfig(enabled=True, url="http://proxy:8080")
        handlers = get_urllib_proxy_handlers(config)

        self.assertEqual(handlers["http"], "http://proxy:8080")
        self.assertEqual(handlers["https"], "http://proxy:8080")

    def test_socks_proxy_handlers(self):
        """SOCKS proxy should work in handlers."""
        config = ProxyConfig(enabled=True, url="socks5://proxy:1080")
        handlers = get_urllib_proxy_handlers(config)

        self.assertEqual(handlers["http"], "socks5://proxy:1080")
        self.assertEqual(handlers["https"], "socks5://proxy:1080")


if __name__ == "__main__":
    unittest.main()
