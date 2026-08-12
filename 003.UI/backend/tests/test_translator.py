import json
import unittest
from unittest.mock import MagicMock, patch

from services import translator


class TranslatorTests(unittest.TestCase):
    def setUp(self):
        with translator._cache_lock:
            translator._cache.clear()

    @patch("services.translator.requests.get")
    def test_successful_translation_is_cached(self, get):
        response = MagicMock()
        response.json.return_value = {
            "responseStatus": 200,
            "responseData": {"translatedText": "早上好"},
        }
        response.ok = True
        get.return_value = response

        with patch.object(translator, "TRANSLATION_PROVIDER_ORDER", ("mymemory",)):
            first = translator.translate_with_status("Good morning")
            second = translator.translate_with_status("Good morning")

        self.assertTrue(first["success"])
        self.assertEqual(first["text"], "早上好")
        self.assertEqual(second["provider"], "cache")
        self.assertEqual(get.call_count, 1)

    @patch("services.translator.requests.get", side_effect=translator.requests.RequestException("offline"))
    def test_network_failure_has_explicit_fallback(self, _get):
        with patch.object(translator, "TRANSLATION_PROVIDER_ORDER", ("google",)):
            result = translator.translate_with_status("Network unavailable")
        self.assertFalse(result["success"])
        self.assertEqual(result["text"], "Network unavailable")
        self.assertIn("暂时不可用", result["warning"])

    @patch("services.translator.requests.get")
    def test_google_response_segments_are_joined(self, get):
        response = MagicMock()
        response.json.return_value = [
            [["早上好，", "Good morning,"], ["欢迎上课。", "welcome to class."]]
        ]
        response.ok = True
        get.return_value = response

        with patch.object(translator, "TRANSLATION_PROVIDER_ORDER", ("google",)):
            result = translator.translate_with_status("Good morning, welcome to class.")

        self.assertTrue(result["success"])
        self.assertEqual(result["provider"], "google")
        self.assertEqual(result["text"], "早上好，欢迎上课。")

    @patch("services.translator.requests.post")
    def test_enterprise_gateway_uses_post_json_and_bearer_token(self, post):
        response = MagicMock()
        response.json.return_value = {
            "translated_text": "企业翻译结果",
        }
        response.ok = True
        post.return_value = response

        with (
            patch.object(translator, "TRANSLATION_PROVIDER_ORDER", ("enterprise",)),
            patch.object(translator, "ENTERPRISE_TRANSLATION_API_URL", "https://translate.example.test/v1"),
            patch.object(translator, "ENTERPRISE_TRANSLATION_API_KEY", "secret"),
        ):
            result = translator.translate_with_status("Enterprise translation")

        self.assertTrue(result["success"])
        self.assertEqual(result["provider"], "enterprise")
        request = post.call_args
        self.assertEqual(request.args[0], "https://translate.example.test/v1")
        self.assertEqual(request.kwargs["headers"]["Authorization"], "Bearer secret")
        self.assertEqual(json.loads(request.kwargs["data"]), {
            "text": "Enterprise translation",
            "source": "en",
            "target": "zh-CN",
        })


if __name__ == "__main__":
    unittest.main()
