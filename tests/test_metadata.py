"""Run with: python -m unittest -v test_metadata"""
import contextlib
import copy
import io
from html.parser import HTMLParser
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

import yaml
import metadata


class MetadataTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.data = self.root / "data"
        self.data.mkdir()
        self.composers = [{"id": 1, "path": "Old,_Composer", "name": "A Composer",
                           "wikidata": "Q1339", "sets": 99, "scores": 99}]
        self.sets = [{"id": 7, "composer_id": 1, "path": "Old,_Composer/Work",
                     "name": "A Work", "scores": 99, "date": 1749, "wikidata": "Q310549"}]
        self.scores = [{"id": 12, "set_id": 7, "path": "New,_Composer/Work,_Op.1/01", "name": "First"},
                       {"id": 13, "set_id": 7, "path": "New,_Composer/Work,_Op.1/02", "name": "Second"}]
        self.write()

    def tearDown(self):
        self.tmp.cleanup()

    def write(self):
        for table in ("composers", "sets", "scores"):
            text = yaml.safe_dump(getattr(self, table), sort_keys=False, allow_unicode=True)
            if table == "sets":
                text = text.replace("date: 1749", "date: 1749  # completion; preserve this note")
            (self.data / f"{table}.yaml").write_text(text, encoding="utf-8")

    def snapshot(self):
        return {p.name: p.read_bytes() for p in self.data.glob("*.yaml")}

    def clean(self):
        result = metadata.reconcile_metadata(self.data, overwrite=True)
        self.assertFalse(result.errors, result.errors)
        return result

    def test_check_then_write_preserves_identity_scores_comments_and_is_idempotent(self):
        before = self.snapshot()
        report = metadata.reconcile_metadata(self.data)
        self.assertFalse(report.errors)
        self.assertEqual(5, len(report.changes))
        self.assertEqual(before, self.snapshot())
        self.clean()
        self.assertEqual(before["scores.yaml"], self.snapshot()["scores.yaml"])
        self.assertIn("date: 1749  # completion; preserve this note", (self.data / "sets.yaml").read_text())
        composers = yaml.safe_load((self.data / "composers.yaml").read_text())
        self.assertEqual((1, "Q1339", 1, 2), tuple(composers[0][k] for k in ("id", "wikidata", "sets", "scores")))
        after = self.snapshot()
        report = self.clean()
        self.assertFalse(report.changes)
        self.assertFalse(report.written)
        self.assertEqual(after, self.snapshot())

    def test_missing_derived_fields_are_inserted_without_losing_comments(self):
        del self.composers[0]["sets"]
        del self.composers[0]["scores"]
        del self.sets[0]["scores"]
        self.sets.append(dict(self.sets[0], id=8, path="New,_Composer/Other"))
        self.scores.append(dict(self.scores[0], id=14, set_id=8, path="New,_Composer/Other"))
        self.write()
        self.clean()
        report = metadata.reconcile_metadata(self.data)
        self.assertFalse(report.changes)
        self.assertFalse(report.errors)
        self.assertEqual([2, 1], [r["scores"] for r in report.tables["sets"]])

    def test_foreign_key_errors_block_every_write(self):
        for table, key, value in [("scores", "set_id", 999), ("sets", "composer_id", 999)]:
            with self.subTest(table=table):
                records = getattr(self, table)
                old = records[0][key]
                records[0][key] = value
                self.write()
                before = self.snapshot()
                report = metadata.reconcile_metadata(self.data, overwrite=True)
                self.assertTrue(report.errors)
                self.assertFalse(report.written)
                self.assertEqual(before, self.snapshot())
                records[0][key] = old

    def test_conflicting_paths_and_duplicate_keys_ids_paths_block_write(self):
        original = copy.deepcopy(self.scores)
        for kind in ("conflict", "duplicate-id", "duplicate-path", "duplicate-key", "escape", "bool-id"):
            with self.subTest(kind=kind):
                self.scores = copy.deepcopy(original)
                if kind == "conflict": self.scores[1]["path"] = "New,_Composer/Other/02"
                if kind == "duplicate-id": self.scores[1]["id"] = 12
                if kind == "duplicate-path": self.scores[1]["path"] = self.scores[0]["path"]
                if kind == "escape": self.scores[0]["path"] = "../Work/01"
                if kind == "bool-id": self.scores[0]["id"] = True
                self.write()
                if kind == "duplicate-key":
                    path = self.data / "scores.yaml"
                    path.write_text(path.read_text().replace("set_id: 7", "set_id: 7\n  set_id: 7", 1))
                before = self.snapshot()
                report = metadata.reconcile_metadata(self.data, overwrite=True)
                self.assertTrue(report.errors)
                self.assertEqual(before, self.snapshot())

    def test_inferred_parent_path_collision_is_not_repaired(self):
        self.sets.append(dict(self.sets[0], id=8, path="Old,_Composer/Other"))
        self.scores[1]["set_id"] = 8
        self.write()
        before = self.snapshot()
        result = metadata.reconcile_metadata(self.data, overwrite=True)
        self.assertTrue(any("collide" in s for s in result.errors))
        self.assertEqual(before, self.snapshot())

    def test_single_work_and_nan_names_render_cleanly_and_urls_are_encoded(self):
        self.scores = [{"id": 12, "set_id": 7, "path": "New,_Composer/D'un_matin", "name": float("nan")}]
        self.write()
        self.clean()
        md, html = metadata.make_contents(self.data, base_url="https://example.org/tree/main/data")
        text = html.read_text()
        self.assertIn("Complete work", text)
        self.assertIn("New%2C_Composer/D%27un_matin", text)
        self.assertNotIn(">nan<", text)
        self.assertNotIn("jquery", text.lower())
        self.assertNotIn("<script src=", text)
        self.assertTrue(md.exists())

    def test_filesystem_checks_and_only_existing_downloads(self):
        corpus = self.root / "corpus"
        for score in self.scores:
            folder = corpus / score["path"]
            folder.mkdir(parents=True)
            (folder / "Score (test).mscz").write_text("fixture")
        (corpus / self.scores[0]["path"] / "Score (test).mxl").write_text("fixture")
        result = metadata.reconcile_metadata(self.data, overwrite=True, corpus_root=corpus)
        self.assertFalse(result.errors)
        _, html = metadata.make_contents(self.data, corpus_root=corpus)
        text = html.read_text()
        self.assertIn("Score%20%28test%29.mscz", text)
        self.assertIn("Score%20%28test%29.mxl", text)
        self.assertNotIn("_melody.mxl", text)
        (corpus / self.scores[0]["path"] / "Score (test).mscz").unlink()
        result = metadata.reconcile_metadata(self.data, corpus_root=corpus)
        self.assertTrue(any("no .mscz" in e for e in result.errors))

    def test_missing_corpus_blocks_reconciliation(self):
        before = self.snapshot()
        result = metadata.reconcile_metadata(self.data, overwrite=True, corpus_root=self.root / "missing")
        self.assertTrue(result.errors)
        self.assertEqual(before, self.snapshot())

    def test_symlink_escape_is_rejected(self):
        corpus = self.root / "corpus"
        corpus.mkdir()
        outside = self.root / "outside"
        outside.mkdir()
        (corpus / "New,_Composer").symlink_to(outside, target_is_directory=True)
        result = metadata.reconcile_metadata(self.data, corpus_root=corpus)
        self.assertTrue(any("outside corpus" in e for e in result.errors))

    def test_html_escapes_metadata_and_rejects_script_urls(self):
        self.sets[0]["name"] = '<script>alert("x")</script>'
        self.sets[0]["imslp_link"] = 'javascript:alert(1)'
        self.scores[0]["name"] = '<img src=x onerror="alert(1)">'
        self.write()
        self.clean()
        _, html = metadata.make_contents(self.data)
        text = html.read_text()
        self.assertNotIn('<script>alert', text)
        self.assertNotIn('<img src=x', text)
        self.assertNotIn('href="javascript:', text)
        self.assertIn('&lt;script&gt;', text)
        with self.assertRaises(metadata.MetadataError):
            metadata.make_contents(self.data, base_url="javascript:alert(1)")

    def test_cli_exit_codes_build_gate_and_separate_scores_input(self):
        alt = self.root / "scores(1).yaml"
        (self.data / "scores.yaml").rename(alt)
        args = ["--data-dir", str(self.data), "--scores", str(alt)]
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(1, metadata.main(args + ["--build"]))
            self.assertFalse((self.data / "README.html").exists())
            self.assertEqual(0, metadata.main(args + ["--write", "--build"]))
            self.assertTrue((self.data / "README.html").exists())
            self.assertEqual(0, metadata.main(args))


class CatalogueJavaScriptTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("node"), "Node.js is needed to execute the generated JavaScript")
    def test_generated_catalogue_controls(self):
        class Parser(HTMLParser):
            def __init__(self):
                super().__init__()
                self.rows, self.script, self.in_script = [], "", False
            def handle_starttag(self, tag, attrs):
                attrs = dict(attrs)
                if tag == "tr" and "data-id" in attrs:
                    self.rows.append({re.sub(r"-([a-z])", lambda m: m[1].upper(), k[5:]): v
                                      for k, v in attrs.items() if k.startswith("data-")})
                if tag == "script": self.in_script = True
            def handle_endtag(self, tag):
                if tag == "script": self.in_script = False
            def handle_data(self, data):
                if self.in_script: self.script += data
        import re
        root = Path(__file__).resolve().parent
        with tempfile.TemporaryDirectory() as temp:
            _, html = metadata.make_contents(root / "data", output_dir=Path(temp),
                                              base_url="https://github.com/MarkGotham/Hauptstimme/tree/main/data")
            parser = Parser()
            parser.feed(html.read_text())
            result = subprocess.run(["node", str(root / "test_catalogue.js")],
                                    input=json.dumps({"rows": parser.rows, "script": parser.script}),
                                    text=True, capture_output=True)
            self.assertEqual(0, result.returncode, result.stderr)
            print(result.stdout.strip())


if __name__ == "__main__":
    unittest.main()
