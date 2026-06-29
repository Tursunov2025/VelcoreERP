"""CORS configuration unit tests."""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

BACKEND = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND))

from config.production import (  # noqa: E402
    LOCALHOST_ORIGIN_REGEX,
    VELCORE_DEV_ORIGINS,
    VELCORE_PRODUCTION_ORIGINS,
    cors_allow_credentials,
    cors_dev_origins_enabled,
    get_cors_origin_regex,
    parse_cors_origins,
)


class CorsConfigTests(unittest.TestCase):
    def setUp(self) -> None:
        self._env = os.environ.copy()

    def tearDown(self) -> None:
        os.environ.clear()
        os.environ.update(self._env)

    def test_wildcard_in_development(self) -> None:
        os.environ["ENVIRONMENT"] = "development"
        os.environ["CORS_ORIGINS"] = "*"
        self.assertEqual(parse_cors_origins(), ["*"])
        self.assertFalse(cors_allow_credentials(["*"]))

    def test_production_explicit_with_dev_flag(self) -> None:
        os.environ["ENVIRONMENT"] = "production"
        os.environ["CORS_ORIGINS"] = "https://erp.velcore.uz"
        os.environ["CORS_ALLOW_DEV"] = "true"
        origins = parse_cors_origins()
        self.assertIn("https://erp.velcore.uz", origins)
        self.assertIn("http://localhost:54847", origins)
        self.assertIn("http://127.0.0.1:54847", origins)
        self.assertEqual(get_cors_origin_regex(), LOCALHOST_ORIGIN_REGEX)
        self.assertTrue(cors_allow_credentials(origins))

    def test_production_without_dev_flag_no_localhost(self) -> None:
        os.environ["ENVIRONMENT"] = "production"
        os.environ["CORS_ORIGINS"] = "https://erp.velcore.uz"
        os.environ["CORS_ALLOW_DEV"] = "false"
        origins = parse_cors_origins()
        self.assertIn("https://erp.velcore.uz", origins)
        self.assertNotIn("http://localhost:54847", origins)
        self.assertIsNone(get_cors_origin_regex())

    def test_production_wildcard_rejected(self) -> None:
        os.environ["ENVIRONMENT"] = "production"
        os.environ["CORS_ORIGINS"] = "*"
        os.environ["CORS_ALLOW_DEV"] = "false"
        origins = parse_cors_origins()
        self.assertNotIn("*", origins)
        self.assertIn("https://erp.velcore.uz", origins)

    def test_dev_origins_list_complete(self) -> None:
        required = {
            "http://localhost:3000",
            "http://localhost:5000",
            "http://localhost:54847",
            "http://127.0.0.1:3000",
            "http://127.0.0.1:5000",
            "http://127.0.0.1:54847",
        }
        self.assertTrue(required.issubset(set(VELCORE_DEV_ORIGINS)))
        self.assertIn("https://erp.velcore.uz", VELCORE_PRODUCTION_ORIGINS)


if __name__ == "__main__":
    unittest.main()
