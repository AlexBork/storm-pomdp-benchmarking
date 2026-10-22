"""Failure causes must not enter the numerical resolution distributions."""
import csv
import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import discretisation_visuals as visuals
import postprocess as p


class DiscretisationFailureTests(unittest.TestCase):
    def test_quality_gap_uses_the_best_bound_and_includes_zero_gain_instances(self):
        benchmarks = [{"id": name, "property": {"dir": direction}} for name, direction in (
            ("max", "max"), ("min", "min"), ("zero", "max"),
            ("unchanged", "max"), ("no-mdp", "max"))]
        execution = {"storm": {"mdp": {
            name: {"result": bound, "wallclock-time": 0.1}
            for name, bound in (("max", "1"), ("min", "2"), ("zero", "0"), ("unchanged", "0.5"))
        }}}
        for resolution in visuals.RESOLUTIONS:
            for mode in ("s", "d"):
                execution["storm"][f"discr{resolution:03}{mode}"] = {
                    name: {"result": bound, "wallclock-time": 1}
                    for name, bound in (("max", "≤ 0.8"), ("min", "≥ 4"),
                                        ("zero", "0"), ("unchanged", "≤ 0.5"), ("no-mdp", "≤ 0.7"))
                }
        execution["storm"]["discr012s"]["max"]["result"] = "≤ 0.6"
        execution["storm"]["discr012s"]["min"]["result"] = "≥ 6"
        # Tighter archived dynamic bounds must not influence the reference.
        execution["storm"]["discr012d"]["max"]["result"] = "≤ 0.1"
        execution["storm"]["discr012d"]["min"]["result"] = "≥ 10"
        execution["storm"]["discr011s"]["max"] = {
            "result": "0", "timeout": True, "wallclock-time": 900}
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(p, "OUT_DIR", directory), \
             patch.object(p.benchmarks, "INSTANCES", benchmarks):
            result = visuals.save_outputs(p, execution, {b["id"]: {} for b in benchmarks}, 900)
            root = Path(directory) / "discretisation-plots"
            with (root / "discretisation_observations.csv").open() as stream:
                rows = list(csv.DictReader(stream, delimiter="\t"))
            first = {r["instance"]: r for r in rows if r["resolution"] == "2" and r["mode"] == "static"}
            self.assertEqual(result["quality-cohort"], 5)
            self.assertEqual({row["mode"] for row in rows}, {"static"})
            self.assertEqual(len(rows), 5 * len(visuals.RESOLUTIONS))
            self.assertAlmostEqual(float(first["max"]["best-bound"]), 0.6)
            self.assertAlmostEqual(float(first["max"]["relative-gap-percent"]), 25)
            self.assertAlmostEqual(float(first["min"]["best-bound"]), 6)
            self.assertAlmostEqual(float(first["min"]["relative-gap-percent"]), 100 / 3)
            for name in ("zero", "unchanged", "no-mdp"):
                self.assertEqual(float(first[name]["relative-gap-percent"]), 0)
            failed = next(r for r in rows if r["instance"] == "max" and r["resolution"] == "11" and r["mode"] == "static")
            self.assertEqual(failed["relative-gap-percent"], "nan")
            self.assertEqual(float(failed["best-bound"]), 0.6)

    def test_timeout_takes_precedence_over_inferred_memory_failure(self):
        run = {"timeout": True, "memout": True, "return-codes": [-9]}
        self.assertEqual(visuals.run_status(p, run, 900), "timeout")
        self.assertEqual(visuals.run_status(p, {"memout": True, "return-codes": [-9]}, 900), "killed")
        self.assertEqual(visuals.run_status(p, {"memout": True}, 900), "memout")
        self.assertEqual(visuals.run_status(p, None, 900), "not-run")
        self.assertEqual(visuals.run_status(p, {"result": "0", "wallclock-time": 901}, 900), "timeout")

    def test_summary_reconciles_causes_and_boxes_contain_only_successes(self):
        benchmarks = [{"id": f"case{i}", "property": {"dir": "max"}} for i in range(5)]
        success = {"result": "≤ 0.8", "wallclock-time": 1}
        timeout = {"timeout": True, "memout": True, "return-codes": [-9]}
        killed = {"memout": True, "return-codes": [-9]}
        allocation = {"memout": True}
        numerical = {"numerical-error": True, "execution-error": True}
        cases = {"s": [success, timeout, killed, allocation, numerical],
                 "d": [success, success, timeout, killed, numerical]}
        execution = {"storm": {"mdp": {b["id"]: {"result": "1", "wallclock-time": 0.1}
                                        for b in benchmarks}}}
        for resolution in visuals.RESOLUTIONS:
            for mode, runs in cases.items():
                execution["storm"][f"discr{resolution:03}{mode}"] = {
                    b["id"]: run for b, run in zip(benchmarks, runs)}
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(p, "OUT_DIR", directory), \
             patch.object(p.benchmarks, "INSTANCES", benchmarks):
            visuals.save_outputs(p, execution, {b["id"]: {} for b in benchmarks}, 900)
            root = Path(directory) / "discretisation-plots"
            with (root / "discretisation_resolution_summary.csv").open() as stream:
                rows = list(csv.DictReader(stream, delimiter="\t"))
            for row in rows:
                total = sum(int(row[key]) for key in (
                    "successful", "not-run", "timeout", "killed", "allocation-memout",
                    "numerical-error", "other-error"))
                self.assertEqual(total, int(row["eligible"]))
                self.assertEqual(float(row["minimum"]), float(row["maximum"]))
            runtime = [r for r in rows if r["metric"] == "runtime" and r["resolution"] == "2"]
            self.assertEqual([r["successful"] for r in runtime], ["1"])
            self.assertEqual([r["timeout"] for r in runtime], ["1"])
            self.assertEqual([r["killed"] for r in runtime], ["1"])
            self.assertEqual([r["allocation-memout"] for r in runtime], ["1"])
            source = (root / "resolution-runtime-no-legend.tex").read_text()
            self.assertNotIn("extra y tick labels", source)
            self.assertIn("ymax=900", source)
            self.assertNotIn("successful runs", source)
            self.assertNotIn("extra y tick labels", (root / "resolution-quality-no-legend.tex").read_text())
            outcomes = (root / "resolution-outcomes.tex").read_text()
            self.assertIn("ymax=5", outcomes)
            for label in ("successful", "TO", "MO", "ERR"):
                self.assertIn(r"\addlegendentry{" + label + "}", outcomes)
            self.assertNotIn("dynamic", outcomes)

    def test_best_configuration_ignores_archived_dynamic_runs(self):
        benchmark = p.benchmarks.INSTANCES[0]
        instance = benchmark["id"]
        relation = p.expected_bound_relation("discr", benchmark)
        static_value, dynamic_value = ((2, 3) if relation == "≥" else (0.8, 0.6))
        static = {"id": "static", "configuration-id": "discr002s",
                  "result": f"{relation} {static_value}", "wallclock-time": 2}
        dynamic = {"id": "dynamic", "configuration-id": "discr012d",
                   "result": f"{relation} {dynamic_value}", "wallclock-time": 1}
        execution = {"storm": {"discr002s": {instance: static},
                               "discr012d": {instance: dynamic}}}
        p.process_meta_configs(execution, {instance: {}})
        selected = execution["storm"]["discr-best-in-900s"][instance]
        self.assertEqual(selected["configuration-id"], "discr002s")
        discretisation = [cfg for cfg in p.storm.CONFIGS if cfg["family"] == "discretisation"]
        self.assertEqual(len(discretisation), 11)
        self.assertTrue(all("--triangulationmode static" in cfg["cmd"] for cfg in discretisation))

    def test_gather_skips_retired_dynamic_logs_before_parsing(self):
        instance = p.benchmarks.INSTANCES[0]["id"]
        with tempfile.TemporaryDirectory() as directory:
            for config in ("discr002s", "discr002d"):
                metadata = {"id": config, "tool": "storm", "configuration-id": config,
                            "benchmark-id": instance, "log": config + ".log"}
                (Path(directory) / (config + ".json")).write_text(json.dumps(metadata))
            with patch.object(p, "parse_tool_output") as parse, \
                 contextlib.redirect_stdout(io.StringIO()):
                execution, _ = p.gather_execution_data([directory], silent=True)
            self.assertEqual(set(execution["storm"]), {"discr002s"})
            parse.assert_called_once()
            self.assertEqual(parse.call_args[0][0]["configuration-id"], "discr002s")


if __name__ == "__main__":
    unittest.main()
