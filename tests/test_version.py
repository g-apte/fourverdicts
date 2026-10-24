import tomllib
import unittest
from pathlib import Path

import fourverdicts


class VersionTests(unittest.TestCase):
    def test_package_version_matches_pyproject(self):
        pyproject = Path(__file__).resolve().parent.parent / "pyproject.toml"
        declared = tomllib.loads(pyproject.read_text(encoding="utf-8"))["project"]["version"]
        self.assertEqual(fourverdicts.__version__, declared)


if __name__ == "__main__":
    unittest.main()
