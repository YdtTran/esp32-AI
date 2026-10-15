"""Metadata compatibility checks for cross-module interface ownership."""

from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from validate import validate_registry


class RegistryTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        specification = self.root / "contracts/diagnostic/v1/spec.md"
        specification.parent.mkdir(parents=True)
        specification.write_text("Test-only specification", encoding="utf-8")
        self.registry = {
            "format_version": 1,
            "interfaces": [{"id": "diagnostic", "version": "1.0.0",
                            "specification": "contracts/diagnostic/v1/spec.md",
                            "producers": ["firmware"], "consumers": ["models"]}],
        }

    def test_repository_registry(self):
        root = Path(__file__).resolve().parents[2]
        validate_registry(json.loads((root / "contracts/registry.json").read_text(encoding="utf-8")), root)

    def test_valid_cross_module_entry(self):
        validate_registry(self.registry, self.root)

    def test_unknown_or_missing_owners_rejected(self):
        for owners in ([], ["unknown"], ["firmware", "firmware"], [None]):
            with self.subTest(owners=owners), self.assertRaises(ValueError):
                entry = deepcopy(self.registry)
                entry["interfaces"][0]["producers"] = owners
                validate_registry(entry, self.root)

    def test_duplicate_interface_version_rejected(self):
        self.registry["interfaces"].append(deepcopy(self.registry["interfaces"][0]))
        with self.assertRaises(ValueError):
            validate_registry(self.registry, self.root)

    def test_missing_or_outside_specification_rejected(self):
        for reference in ("contracts/missing.md", "../outside.md", "models/spec.md"):
            with self.subTest(reference=reference), self.assertRaises(ValueError):
                entry = deepcopy(self.registry)
                entry["interfaces"][0]["specification"] = reference
                validate_registry(entry, self.root)

    def test_unsupported_metadata_version_rejected(self):
        self.registry["format_version"] = 2
        with self.assertRaises(ValueError):
            validate_registry(self.registry, self.root)

