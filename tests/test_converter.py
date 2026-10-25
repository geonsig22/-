import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image
from converter import convert


class ConversionTests(unittest.TestCase):
    def test_target_size_for_all_formats(self):
        import random
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "noise.png"
            Image.frombytes("RGB", (256, 256), random.Random(1).randbytes(256 * 256 * 3)).save(source)
            for output in ("JPG", "PNG", "WebP"):
                result = convert(source, folder, output, 90, 0, 10)
                self.assertLessEqual(result.stat().st_size, 10 * 1024)
                with Image.open(result) as image:
                    image.load()
                    self.assertGreater(image.width, 0)

    def test_resize_transparency_and_preserve_original(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "photo.png"
            Image.new("RGBA", (100, 50), (255, 0, 0, 0)).save(source)
            original = source.read_bytes()
            result = convert(source, folder, "JPG", 85, 40)
            with Image.open(result) as image:
                self.assertEqual(image.size, (40, 20))
                self.assertEqual(image.mode, "RGB")
                self.assertGreater(min(image.getpixel((0, 0))), 250)
            self.assertEqual(source.read_bytes(), original)
            second = convert(source, folder, "JPG")
            self.assertNotEqual(result, second)

    def test_formats_and_no_upscale(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "photo.png"
            Image.new("RGB", (12, 8), "red").save(source)
            for output in ("PNG", "WebP"):
                result = convert(source, folder, output, 80, 100)
                self.assertNotEqual(source, result)
                with Image.open(result) as image:
                    self.assertEqual(image.size, (12, 8))
                    self.assertEqual(image.format, output.upper())

    def test_failed_write_removes_partial_output(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "photo.png"
            Image.new("RGB", (12, 8)).save(source)
            with patch.object(Image.Image, "save", side_effect=OSError("disk full")):
                with self.assertRaises(OSError):
                    convert(source, folder)
            self.assertEqual(list(Path(folder).glob("*.jpg")), [])

    def test_corrupt_input_fails(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "bad.jpg"
            source.write_bytes(b"invalid")
            with self.assertRaises(OSError):
                convert(source, Path(folder) / "out")


if __name__ == "__main__":
    unittest.main()
