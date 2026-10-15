"""Check that package metadata and the src package agree."""

from pathlib import Path
import tomllib
import unittest

import iot_models


class PackageTests(unittest.TestCase):
    def test_version_matches_project_metadata(self):
        metadata = Path(__file__).resolve().parents[1] / "pyproject.toml"
        with metadata.open("rb") as stream:
            project = tomllib.load(stream)["project"]
        self.assertEqual(iot_models.__version__, project["version"])

