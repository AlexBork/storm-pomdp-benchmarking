"""Checks for independent pictures and a single persistent export location."""
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import export_tikzpictures as export
import postprocess as p


class TikzPictureTests(unittest.TestCase):
    def test_scatter_ticks_respect_a_non_decade_time_limit(self):
        options = p.scatter_log_ticks(0.1, 900, failure=2000)
        self.assertIn("xtick={0.1,1,10,100,900,2000}", options)
        self.assertIn("ytick={0.1,1,10,100,900,2000}", options)
        self.assertNotIn("$10^{3}$", options)

    def test_balanced_labels_respect_comments_and_escapes(self):
        source = r"{50\% \{text\} {nested}% ignored }" + "\nend}tail"
        value, end = export.group(source, 0)
        self.assertTrue(value.endswith("\nend"))
        self.assertEqual(source[end:], "tail")

    def test_typography_inherits_without_package_or_externalisation_helpers(self):
        source = (r"\scriptsize\begin{tikzpicture}[scale=0.75,transform shape]\begin{axis}["
                  + r"x label style={font=\small,yshift=4pt},legend style={nodes={scale=0.75,transform shape},inner sep=1pt},"
                  + r"xmin=0,xmax=100]\node[font=\scriptsize] {10};\end{axis}\end{tikzpicture}")
        result = export.inherit_typography(source, "plots/check.tex")
        for override in (r"\scriptsize", r"\small", "scale=0.75", "x label style", r"\POMDP", r"\tikzexternal"):
            self.assertNotIn(override, result)
        self.assertIn("xmin=0,xmax=100", result)
        self.assertIn("legend style=", result)

    def test_intermediate_panels_do_not_persist_and_csvs_are_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            adapter = SimpleNamespace(OUT_DIR="original")
            temporary_roots = []

            def saver(folder):
                def save(p, execution, instances):
                    staging = Path(p.OUT_DIR)
                    temporary_roots.append(staging)
                    (staging / folder).mkdir()
                    (staging / folder / "audit.csv").write_bytes(b"value\tstatus\r\n0\tsuccess\r\n")
                    (staging / folder / "duplicate-panel.tex").write_text("intermediate")
                return save

            def pictures(staging, destination):
                destination.mkdir(parents=True)
                (destination / "figure.tex").write_text("picture")
                return {"tikzpictures": 1}

            with patch("discretisation_visuals.save_outputs", saver("discretisation-plots")), \
                 patch("underapprox_comparison_visuals.save_outputs", saver("underapprox-plots")), \
                 patch("combined_bounds_visuals.save_outputs", saver("combined-bounds-plots")), \
                 patch.object(export, "export_pictures", pictures):
                result = export.generate_plots(adapter, {}, {}, root)
            self.assertEqual(adapter.OUT_DIR, "original")
            self.assertEqual(result["audit-csvs"], 3)
            self.assertTrue(all(not p.exists() for p in temporary_roots))
            self.assertEqual({p.name for p in root.iterdir()}, {"tikzpictures", "plot-data"})
            for csv in (root / "plot-data").rglob("*.csv"):
                self.assertEqual(csv.read_bytes(), b"value\tstatus\r\n0\tsuccess\r\n")
            self.assertEqual(len(list(root.rglob("*.tex"))), 1)

    def test_output_directory_is_restored_if_generation_fails(self):
        adapter = SimpleNamespace(OUT_DIR="original")
        with tempfile.TemporaryDirectory() as directory, \
             patch("discretisation_visuals.save_outputs", side_effect=RuntimeError("failed")):
            with self.assertRaisesRegex(RuntimeError, "failed"):
                export.generate_plots(adapter, {}, {}, Path(directory))
        self.assertEqual(adapter.OUT_DIR, "original")


if __name__ == "__main__":
    unittest.main()
