import tempfile
import unittest
from pathlib import Path

from idiot_chat.context import index_folder


class ContextTests(unittest.TestCase):
    def test_indexes_text_but_not_hidden_binary_or_secrets(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'notes.md').write_text('Useful notes', encoding='utf-8')
            (root / '.env').write_text('KEY=secret')
            (root / 'secrets.txt').write_text('secret')
            (root / 'image.txt').write_bytes(b'abc\x00def')
            (root / 'photo.png').write_bytes(b'image')
            (root / '.git').mkdir()
            (root / '.git' / 'data.txt').write_text('private')
            result = index_folder(root)
            self.assertEqual(result.files, ('notes.md',))
            self.assertIn('Useful notes', result.text)
            self.assertNotIn('secret', result.text)

    def test_truncates_to_total_budget_including_labels(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'a.txt').write_text('A' * 500)
            (root / 'b.txt').write_text('B' * 500)
            result = index_folder(root, max_chars=200, per_file_chars=80)
            self.assertLessEqual(len(result.text), 200)
            self.assertEqual(result.files, ('a.txt', 'b.txt'))
            self.assertTrue(result.truncated)
            self.assertIn('[truncated]', result.text)

    def test_does_not_follow_file_or_directory_symlinks(self):
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as outside:
            root, other = Path(directory), Path(outside)
            (other / 'private.txt').write_text('outside secret')
            (root / 'linked.txt').symlink_to(other / 'private.txt')
            (root / 'linked_dir').symlink_to(other, target_is_directory=True)
            self.assertEqual(index_folder(root).files, ())

    def test_file_and_scan_limits(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for i in range(8):
                (root / ('%s.txt' % i)).write_text('data')
            result = index_folder(root, max_files=2)
            self.assertEqual(len(result.files), 2)
            self.assertTrue(result.truncated)
            result = index_folder(root, max_entries=2)
            self.assertLessEqual(len(result.files), 2)
            self.assertTrue(result.truncated)

    def test_large_utf8_file_is_truncated_not_discarded_at_byte_boundary(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'unicode.txt').write_text('🙂' * 500, encoding='utf-8')
            result = index_folder(root, per_file_chars=50)
            self.assertEqual(result.files, ('unicode.txt',))
            self.assertTrue(result.truncated)
            self.assertIn('[truncated]', result.text)
            self.assertIn('🙂', result.text)

    def test_tiny_budget_and_invalid_folder(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'notes.txt').write_text('hello')
            self.assertLessEqual(len(index_folder(root, max_chars=3).text), 3)
            with self.assertRaises(ValueError):
                index_folder(root / 'missing')


if __name__ == '__main__':
    unittest.main()
