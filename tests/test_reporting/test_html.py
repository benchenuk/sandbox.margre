"""Tests for HTML report generation."""

import json
import pytest
from pathlib import Path
from unittest.mock import patch

from margre.reporting.html import generate_html_report, save_html_report

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "runs" / "test_leonardo"

# html.py calls get_runs_dir, read_run_metadata, and generate_mermaid internally.
# We mock all three so no real filesystem/config is needed.


def _patches(mock_runs_dir):
    """Return a list of patch context managers for all external deps of generate_html_report."""
    return [
        patch("margre.reporting.html.get_runs_dir", return_value=mock_runs_dir),
        patch("margre.reporting.html.read_run_metadata", return_value={
            "seed_person": "Leonardo da Vinci",
            "agents_involved": [
                "agent_0_leonardo_da_vinci",
                "agent_1_leonardo_da_vinci",
            ],
        }),
        patch("margre.reporting.mermaid.get_runs_dir", return_value=mock_runs_dir),
    ]


@pytest.fixture
def mock_runs_dir():
    return FIXTURES_DIR.parent


class TestGenerateHtmlReport:
    """Test generate_html_report using fixture data."""

    def test_html_contains_seed_person_title(self, mock_runs_dir):
        patches = _patches(mock_runs_dir)
        with patches[0], patches[1], patches[2]:
            html = generate_html_report("test_leonardo")
        assert "<title>MARGRe: Leonardo da Vinci</title>" in html
        assert "<h1>Leonardo da Vinci</h1>" in html

    def test_html_contains_run_id(self, mock_runs_dir):
        patches = _patches(mock_runs_dir)
        with patches[0], patches[1], patches[2]:
            html = generate_html_report("test_leonardo")
        assert "<code>test_leonardo</code>" in html

    def test_html_contains_agent_count(self, mock_runs_dir):
        patches = _patches(mock_runs_dir)
        with patches[0], patches[1], patches[2]:
            html = generate_html_report("test_leonardo")
        assert "2 agents" in html

    def test_mermaid_div_present(self, mock_runs_dir):
        patches = _patches(mock_runs_dir)
        with patches[0], patches[1], patches[2]:
            html = generate_html_report("test_leonardo")
        assert 'class="mermaid"' in html
        assert "mindmap" in html

    def test_marked_js_referenced(self, mock_runs_dir):
        patches = _patches(mock_runs_dir)
        with patches[0], patches[1], patches[2]:
            html = generate_html_report("test_leonardo")
        assert "marked" in html

    def test_mermaid_js_referenced(self, mock_runs_dir):
        patches = _patches(mock_runs_dir)
        with patches[0], patches[1], patches[2]:
            html = generate_html_report("test_leonardo")
        assert "mermaid" in html

    def test_markdown_script_tag_present(self, mock_runs_dir):
        patches = _patches(mock_runs_dir)
        with patches[0], patches[1], patches[2]:
            html = generate_html_report("test_leonardo")
        assert 'id="report-md"' in html
        assert 'type="text/markdown"' in html

    def test_files_section_has_aggregation_link(self, mock_runs_dir):
        patches = _patches(mock_runs_dir)
        with patches[0], patches[1], patches[2]:
            html = generate_html_report("test_leonardo")
        assert 'href="aggregation.json"' in html

    def test_files_section_has_agent_links(self, mock_runs_dir):
        patches = _patches(mock_runs_dir)
        with patches[0], patches[1], patches[2]:
            html = generate_html_report("test_leonardo")
        assert "agent_0_leonardo_da_vinci.json" in html
        assert "agent_1_leonardo_da_vinci.json" in html

    def test_empty_run_produces_valid_html(self, tmp_path):
        """A run with no agent JSONs should produce valid HTML with no graph."""
        empty_run = tmp_path / "empty_run"
        empty_run.mkdir()
        (empty_run / "agents").mkdir()
        (empty_run / "aggregation.json").write_text(
            json.dumps({"seed_person": "Unknown Person", "agents_involved": []})
        )
        meta = {"seed_person": "Unknown Person", "agents_involved": []}
        with (
            patch("margre.reporting.html.get_runs_dir", return_value=tmp_path),
            patch("margre.reporting.html.read_run_metadata", return_value=meta),
            patch("margre.reporting.mermaid.get_runs_dir", return_value=tmp_path),
        ):
            html = generate_html_report("empty_run")
        assert "<title>MARGRe: Unknown Person</title>" in html
        assert "<h1>Unknown Person</h1>" in html
        assert "0 agents" in html
        # Mindmap div is present (even for a single seed node)
        assert 'class="mermaid"' in html

    def test_run_with_report_embeds_content(self, tmp_path):
        """A run with final_report.md should embed the content in the script tag."""
        run_dir = tmp_path / "report_run"
        run_dir.mkdir()
        (run_dir / "agents").mkdir()
        report_content = "# Test Report\n\nHello world."
        (run_dir / "final_report.md").write_text(report_content)
        (run_dir / "aggregation.json").write_text(
            json.dumps({"seed_person": "Test Person", "agents_involved": []})
        )
        meta = {"seed_person": "Test Person", "agents_involved": []}
        with (
            patch("margre.reporting.html.get_runs_dir", return_value=tmp_path),
            patch("margre.reporting.html.read_run_metadata", return_value=meta),
            patch("margre.reporting.mermaid.get_runs_dir", return_value=tmp_path),
        ):
            html = generate_html_report("report_run")
        assert "Hello world." in html


class TestSaveHtmlReport:
    def test_writes_file(self, mock_runs_dir):
        """save_html_report should write a .html file and return its path."""
        import shutil
        with (
            patch("margre.reporting.html.get_runs_dir", return_value=mock_runs_dir),
            patch("margre.reporting.html.read_run_metadata", return_value={
                "seed_person": "Leonardo da Vinci",
                "agents_involved": [
                    "agent_0_leonardo_da_vinci",
                    "agent_1_leonardo_da_vinci",
                ],
            }),
            patch("margre.reporting.mermaid.get_runs_dir", return_value=mock_runs_dir),
        ):
            # Use a temp copy so we don't pollute the fixture
            import tempfile
            with tempfile.TemporaryDirectory() as tmp:
                tmp_path = Path(tmp)
                run_dir = tmp_path / "test_leonardo"
                shutil.copytree(FIXTURES_DIR, run_dir)

                with (
                    patch("margre.reporting.html.get_runs_dir", return_value=tmp_path),
                    patch("margre.reporting.html.read_run_metadata", return_value={
                        "seed_person": "Leonardo da Vinci",
                        "agents_involved": [
                            "agent_0_leonardo_da_vinci",
                            "agent_1_leonardo_da_vinci",
                        ],
                    }),
                    patch("margre.reporting.mermaid.get_runs_dir", return_value=tmp_path),
                ):
                    path = save_html_report("test_leonardo")

                assert Path(path).exists()
                assert Path(path).name == "report.html"
                content = Path(path).read_text(encoding="utf-8")
                assert "Leonardo da Vinci" in content

    def test_content_matches_generate(self, mock_runs_dir):
        """The saved file should match what generate_html_report produces."""
        import shutil
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            run_dir = tmp_path / "test_leonardo"
            shutil.copytree(FIXTURES_DIR, run_dir)

            meta = {
                "seed_person": "Leonardo da Vinci",
                "agents_involved": [
                    "agent_0_leonardo_da_vinci",
                    "agent_1_leonardo_da_vinci",
                ],
            }
            with (
                patch("margre.reporting.html.get_runs_dir", return_value=tmp_path),
                patch("margre.reporting.html.read_run_metadata", return_value=meta),
                patch("margre.reporting.mermaid.get_runs_dir", return_value=tmp_path),
            ):
                generated = generate_html_report("test_leonardo")
                saved_path = save_html_report("test_leonardo")

            saved_content = Path(saved_path).read_text(encoding="utf-8")
            assert saved_content == generated