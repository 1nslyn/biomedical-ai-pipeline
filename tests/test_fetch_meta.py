"""fetch_meta.py must emit a stub that is valid YAML whatever Crossref returns."""
import importlib.util
import sys
import unittest
from pathlib import Path

import yaml

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))
_spec = importlib.util.spec_from_file_location("fetch_meta", SCRIPTS / "fetch_meta.py")
fetch_meta = importlib.util.module_from_spec(_spec)
sys.modules["fetch_meta"] = fetch_meta
_spec.loader.exec_module(fetch_meta)


def render(title: str) -> str:
    return fetch_meta.TEMPLATE.format(
        notes="",
        date="2026-08",
        title=fetch_meta.yaml_scalar(title),
        url="https://doi.org/10.1038/x",
        doi="10.1038/x",
        venue=fetch_meta.yaml_scalar("Nat. Biomed. Eng."),
        first_name=fetch_meta.yaml_scalar("Xiangde Luo"),
        last_name=fetch_meta.yaml_scalar("Ruijiang Li"),
        added="2026-09",
    )


class YamlScalarTests(unittest.TestCase):
    def test_plain_title_stays_plain(self):
        self.assertEqual(fetch_meta.yaml_scalar("A whole-slide foundation model"), "A whole-slide foundation model")

    def test_colon_title_is_quoted(self):
        title = "nnMIL: a generalizable multiple instance learning framework"
        self.assertEqual(fetch_meta.yaml_scalar(title), '"nnMIL: a generalizable multiple instance learning framework"')

    def test_quoted_forms_round_trip(self):
        for s in [
            "nnMIL: a generalizable framework",
            "Deep learning #1 in pathology",
            "- a title starting with a dash",
            "2024",
            "true",
            'A "quoted" word and a \\ backslash',
            "Trailing colon:",
            "",
        ]:
            with self.subTest(s=s):
                self.assertEqual(yaml.safe_load(f"k: {fetch_meta.yaml_scalar(s)}")["k"], s)

    def test_rendered_stub_parses_and_keeps_title(self):
        title = "nnMIL: a generalizable multiple instance learning framework for computational pathology"
        doc = yaml.safe_load(render(title))
        self.assertIsInstance(doc, list)
        self.assertEqual(doc[0]["title"], title)
        self.assertEqual(doc[0]["authors"]["first"]["name"], "Xiangde Luo")


if __name__ == "__main__":
    unittest.main()
