"""Offline regression tests for deterministic text conversion paths.

Every input is generated inside a temporary directory.  The suite does not use
vault content, provider calls, OCR, Qdrant, or machine-local configuration.
"""

import tempfile
import unittest
from pathlib import Path

from convert import ConversionError, _convert_text, convert_to_markdown


class TextConversionTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name)

    def test_utf8_text_is_returned_unchanged(self):
        expected = "Synthetic UTF-8 text.\nSecond line: café.\n"
        source = self.root / "example.txt"
        source.write_text(expected, encoding="utf-8")

        self.assertEqual(convert_to_markdown(str(source)), expected)

    def test_gbk_text_uses_the_encoding_fallback(self):
        expected = "合成的 GBK 编码测试。\n"
        source = self.root / "example.txt"
        source.write_bytes(expected.encode("gbk"))

        self.assertEqual(_convert_text(str(source)), expected)

    def test_markdown_without_images_is_returned_unchanged(self):
        expected = "# Synthetic note\n\nNo image references are present.\n"
        source = self.root / "example.md"
        source.write_text(expected, encoding="utf-8")

        self.assertEqual(convert_to_markdown(str(source)), expected)

    def test_missing_source_raises_conversion_error(self):
        missing = self.root / "missing.txt"

        with self.assertRaisesRegex(ConversionError, "文件不存在"):
            convert_to_markdown(str(missing))

    def test_unsupported_extension_raises_conversion_error(self):
        source = self.root / "example.xyz"
        source.write_text("synthetic input", encoding="utf-8")

        with self.assertRaisesRegex(ConversionError, "不支持的文件类型: \\.xyz"):
            convert_to_markdown(str(source))


if __name__ == "__main__":
    unittest.main()
