"""Checks for portable exports and failure-status semantics."""
import contextlib
import gzip
from html.parser import HTMLParser
import io
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import html_results as export
import postprocess as p


class TableParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.runs = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "td" and "data-status" in attrs:
            self.runs.append(attrs)


class HtmlResultsTests(unittest.TestCase):
    def test_timeout_and_kill_are_not_memory_errors(self):
        self.assertEqual(export.runtime_status(p, {"timeout": True, "return-codes": [-9], "memout": True}), "timeout")
        self.assertEqual(export.runtime_status(p, {"return-codes": [-9], "memout": True}), "killed")
        self.assertEqual(export.runtime_status(p, {"memout": True}), "memout")
        self.assertEqual(export.runtime_status(p, {"result": "0"}), "successful")
        self.assertEqual(export.runtime_status(p, None), "missing")

    def test_large_log_is_escaped_bounded_and_losslessly_compressed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.log"
            raw = b"<script>alert('log')</script>\n" + b"large log\n" * 20000 + b"tail: \xff"
            source.write_bytes(raw)
            destination = root / "run.html"
            run = {"id": "run", "benchmark-id": "benchmark", "tool": "storm",
                   "configuration-id": "cut08", "result": "0", "log": str(source),
                   "commands": ["storm <model>"]}
            export.run_page(p, run, destination)
            page = destination.read_text()
            self.assertIn("&lt;script&gt;", page)
            self.assertNotIn("<script>", page)
            self.assertIn("middle of log omitted", page)
            self.assertIn("tail:", page)
            self.assertLess(len(page), 100000)
            self.assertEqual(gzip.decompress((root / "run.log.gz").read_bytes()), raw)

    def test_clipping_correctness_exception_has_its_own_failure_status(self):
        run = {"id": "clipping-run", "return-codes": [1], "timeout": False,
               "execution-error": True, "result": "0"}
        log = "Grid clipping LP returned a clipping value of zero for distinct beliefs"
        with contextlib.redirect_stdout(io.StringIO()):
            p.storm.parse_logfile(log, run)
        self.assertTrue(run["numerical-error"])
        self.assertFalse(p.is_successful_result(run))
        self.assertEqual(export.runtime_status(p, run), "numerical-error")

    def test_parsing_preserves_source_log_bytes_and_mtime(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "run.log"
            source.write_bytes(b"original measurement\n")
            before = source.read_bytes(), source.stat().st_mtime_ns
            run = {"log": str(source), "invocation-note": "parsed note", "tool": "storm",
                   "benchmark-id": p.benchmarks.INSTANCES[0]["id"], "configuration-id": "cut08"}
            with patch.object(p.storm, "parse_logfile"):
                p.parse_tool_output(run)
            self.assertEqual((source.read_bytes(), source.stat().st_mtime_ns), before)
            self.assertEqual(run["notes"], ["parsed note"])

    def test_missing_source_log_keeps_run_details_available(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "missing.html"
            export.run_page(p, {"id": "run", "tool": "storm", "configuration-id": "cut08",
                                "benchmark-id": "model", "log": str(Path(directory) / "absent")}, destination)
            self.assertIn("Source log unavailable", destination.read_text())

    def test_export_includes_early_failures_and_excludes_derived_selections(self):
        with tempfile.TemporaryDirectory() as directory:
            benchmark = {"id": "crypt6_maxpackets", "name": "crypt", "benchmark-set": "crypt6",
                         "property": {"type": "rew", "dir": "max", "id": "rewmaxpackets"}}
            configurations = [{"id": "mdp", "family": "MDP"},
                              {"id": "cut08", "family": "cutoff"},
                              {"id": "clip08res02", "family": "clipping"}]
            mdp = {"id": "mdp-run", "tool": "storm", "configuration-id": "mdp",
                   "benchmark-id": benchmark["id"], "result": "1", "wallclock-time": 1}
            killed = {"id": "cut-run", "tool": "storm", "configuration-id": "cut08",
                      "benchmark-id": benchmark["id"], "execution-error": True,
                      "return-codes": [-9], "memout": True, "wallclock-time": 2}
            execution = {"storm": {"mdp": {benchmark["id"]: mdp},
                                   "cut08": {benchmark["id"]: killed},
                                   "cut-best-in-1800s": {benchmark["id"]: killed}}}
            adapter = SimpleNamespace(TOOLS=[SimpleNamespace(NAME="storm", CONFIGS=configurations,
                                                            RETIRED_CONFIG_IDS={"discr002d"})],
                                      benchmarks=SimpleNamespace(INSTANCES=[benchmark]),
                                      get_result=p.get_result, is_successful_result=p.is_successful_result,
                                      parse_result_value=p.parse_result_value, comparison_value=p.comparison_value)
            logs = Path(directory) / "logs"
            logs.mkdir()
            retired = [logs / f"storm.discr002d.{benchmark['id']}{suffix}"
                       for suffix in (".html", ".log.gz")]
            for artifact in retired:
                artifact.write_text("obsolete generated artifact")
            with contextlib.redirect_stdout(io.StringIO()):
                summary = export.save_results(adapter, execution, {}, output_dir=directory)
            self.assertTrue(all(not artifact.exists() for artifact in retired))
            self.assertEqual(summary["runs"], 2)
            self.assertEqual(summary["seconds"], 3)
            page = (Path(directory) / "index.html").read_text()
            parser = TableParser()
            parser.feed(page)
            self.assertCountEqual([cell["data-status"] for cell in parser.runs],
                                  ["successful", "killed", "missing"])
            self.assertIn("rewmaxpackets", page)
            self.assertIn("crypt6", page)
            self.assertIn("≤ 1.0", page)
            self.assertNotIn("cut-best-in-1800s", page)


if __name__ == "__main__":
    unittest.main()
