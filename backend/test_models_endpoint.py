import unittest
import asyncio
from backend.main import get_models


class ModelsEndpointTests(unittest.TestCase):
    def test_models_endpoint_returns_backend_message_schemas(self):
        payload = asyncio.run(get_models())
        self.assertIn("models", payload)

        models = payload["models"]
        self.assertEqual(
            set(models.keys()),
            {"register", "frame", "alert", "ping", "studentStatus", "roster"},
        )
        self.assertEqual(models["register"]["properties"]["type"]["const"], "register")
        self.assertEqual(models["frame"]["properties"]["type"]["const"], "frame")
        self.assertEqual(models["alert"]["properties"]["type"]["const"], "alert")
        self.assertEqual(models["ping"]["properties"]["type"]["const"], "ping")
