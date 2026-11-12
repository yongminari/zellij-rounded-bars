import hashlib
import importlib.util
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location("release_index", "scripts/update-release.py")
index = importlib.util.module_from_spec(spec)
spec.loader.exec_module(index)


class ReleaseIndexTest(unittest.TestCase):
    def test_stable_versions(self):
        self.assertLess(index.version("v0.9.0"), index.version("v0.10.0"))
        for tag in ("v1.0.0-rc1", "main", "1.0.0"):
            with self.assertRaises(ValueError):
                index.version(tag)

    def test_verified_assets_and_corruption(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            checksums = []
            for name in index.ASSETS:
                data = name.encode()
                (root / name).write_bytes(data)
                checksums.append(f"{hashlib.sha256(data).hexdigest()}  {name}")
            (root / "SHA256SUMS").write_text("\n".join(checksums))
            result = index.manifest("v0.1.1", root)
            self.assertEqual(result["version"], "0.1.1")
            self.assertEqual(set(result["artifacts"]), set(index.ASSETS))
            (root / index.ASSETS[0]).write_bytes(b"corrupted")
            with self.assertRaisesRegex(ValueError, "Checksum mismatch"):
                index.manifest("v0.1.1", root)


if __name__ == "__main__":
    unittest.main()
