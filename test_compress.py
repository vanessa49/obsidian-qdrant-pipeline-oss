"""Pure tests for raw-material classification.

Every fixture in this file is fictional, generated in place, and contains no
vault content, transcript, research data, or network call.
"""

import unittest

from compress import get_source_type, is_raw_material, needs_compression


SYNTHETIC_INTERVIEW = "Synthetic interview statement about fictional widgets. " * 160
SYNTHETIC_CHAT = "Synthetic chat message about an imaginary release checklist. " * 160
SYNTHETIC_SHORT_CHAT = "Synthetic chat: confirm the example is disposable."
SYNTHETIC_ARTICLE = "A short public article about a fictional document pipeline."


class RawMaterialClassificationTests(unittest.TestCase):
    def test_interview_is_classified_and_long_enough_to_compress(self):
        self.assertTrue(is_raw_material("synthetic-interview.txt", SYNTHETIC_INTERVIEW))
        self.assertEqual(get_source_type("synthetic-interview.txt"), "interview")
        self.assertTrue(needs_compression(SYNTHETIC_INTERVIEW))

    def test_chat_is_classified_and_long_enough_to_compress(self):
        self.assertTrue(is_raw_material("synthetic-chat.txt", SYNTHETIC_CHAT))
        self.assertEqual(get_source_type("synthetic-chat.txt"), "chat")
        self.assertTrue(needs_compression(SYNTHETIC_CHAT))

    def test_short_chat_is_classified_without_compression(self):
        self.assertTrue(is_raw_material("synthetic-chat.txt", SYNTHETIC_SHORT_CHAT))
        self.assertFalse(needs_compression(SYNTHETIC_SHORT_CHAT))

    def test_regular_article_is_not_raw_material(self):
        self.assertFalse(is_raw_material("synthetic-article.md", SYNTHETIC_ARTICLE))


if __name__ == "__main__":
    unittest.main()
