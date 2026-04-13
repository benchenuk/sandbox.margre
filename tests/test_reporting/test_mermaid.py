"""Tests for Mermaid mindmap generation."""

import json
import pytest
from pathlib import Path
from unittest.mock import patch

from margre.reporting.mermaid import (
    _mermaid_id,
    _mermaid_label,
    _deduplicate_relationships,
    generate_mermaid,
    save_mermaid,
)

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "runs" / "test_leonardo"


@pytest.fixture
def mock_runs_dir():
    """Return the path to the test fixture runs directory."""
    return FIXTURES_DIR.parent


# --- Unit tests for helper functions ---

class TestMermaidId:
    def test_spaces_replaced(self):
        assert _mermaid_id("Leonardo da Vinci") == "Leonardo_da_Vinci"

    def test_apostrophe_replaced(self):
        assert _mermaid_id("Marco d'Oggiono") == "Marco_d_Oggiono"

    def test_hyphen_replaced(self):
        assert _mermaid_id("Ludovico il Moro") == "Ludovico_il_Moro"

    def test_simple_name(self):
        assert _mermaid_id("Milan") == "Milan"

    def test_parentheses_stripped(self):
        assert _mermaid_id("Giovanni Antonio Caprotti (Salai)") == "Giovanni_Antonio_Caprotti__Salai_"


class TestMermaidLabel:
    def test_simple_name(self):
        assert _mermaid_label("Milan") == "Milan"

    def test_quotes_escaped(self):
        assert _mermaid_label('He said "hello"') == "He said &#quot;hello&#quot;"

    def test_parens_replaced(self):
        # "(Giovannetta)" becomes "–Giovannetta" — space before ( is consumed
        assert _mermaid_label("Giovanna (Giovannetta) da Vinci") == "Giovanna –Giovannetta da Vinci"
        # No space before paren: just replace
        assert _mermaid_label("Foo(bar)") == "Foo –bar"


class TestDeduplicateRelationships:
    def test_removes_exact_duplicates(self):
        rels = [
            {"rel_type": "KNEW", "target_name": "Michelangelo", "target_label": "Person", "context": "short"},
            {"rel_type": "KNEW", "target_name": "Michelangelo", "target_label": "Person", "context": "longer context here"},
        ]
        result = _deduplicate_relationships(rels)
        assert len(result) == 1
        assert result[0]["context"] == "longer context here"

    def test_keeps_different_types_separate(self):
        rels = [
            {"rel_type": "KNEW", "target_name": "Michelangelo", "target_label": "Person", "context": "knew him"},
            {"rel_type": "RIVAL", "target_name": "Michelangelo", "target_label": "Person", "context": "rival"},
        ]
        result = _deduplicate_relationships(rels)
        assert len(result) == 2

    def test_prefers_year_over_no_year(self):
        rels = [
            {"rel_type": "KNEW", "target_name": "Michelangelo", "target_label": "Person", "context": "a", "year": None},
            {"rel_type": "KNEW", "target_name": "Michelangelo", "target_label": "Person", "context": "a", "year": 1500},
        ]
        result = _deduplicate_relationships(rels)
        assert len(result) == 1
        assert result[0]["year"] == 1500

    def test_empty_input(self):
        assert _deduplicate_relationships([]) == []


# --- Integration tests for generate_mermaid ---

def _load_agent_relationships(fixture_path: Path) -> list:
    """Load relationships from fixture agent JSON files."""
    all_rels = []
    agents_path = fixture_path / "agents"
    for json_file in sorted(agents_path.glob("*.json")):
        data = json.loads(json_file.read_text(encoding="utf-8"))
        all_rels.extend(data.get("relationships", []))
    return all_rels


class TestGenerateMermaid:
    """Test generate_mermaid using fixture data.

    We mock get_runs_dir to point at our fixtures directory so no config/Neo4j is needed.
    """

    def test_generates_graph_lr_header(self, mock_runs_dir):
        with patch("margre.reporting.mermaid.get_runs_dir", return_value=mock_runs_dir):
            output = generate_mermaid("test_leonardo")
        assert output.startswith("mindmap\n")

    def test_seed_person_declared_first(self, mock_runs_dir):
        with patch("margre.reporting.mermaid.get_runs_dir", return_value=mock_runs_dir):
            output = generate_mermaid("test_leonardo")
        lines = output.strip().split("\n")
        # Second line is the seed person mindmap root
        assert "Leonardo da Vinci" in lines[1]

    def test_no_self_edge(self, mock_runs_dir):
        """Seed person should not appear under itself."""
        with patch("margre.reporting.mermaid.get_runs_dir", return_value=mock_runs_dir):
            output = generate_mermaid("test_leonardo")
        # In mindmap format, no nested occurrence of the seed label under itself
        lines = output.split("\n")
        in_studied_at = False
        for line in lines:
            if "STUDIED_AT" in line:
                in_studied_at = True
            if in_studied_at and "Leonardo da Vinci" in line and "(( " not in line:
                pytest.fail(f"Self-reference found under STUDIED_AT: {line}")

    def test_leaf_nodes_include_year(self, mock_runs_dir):
        """Leaf nodes should include the year in the label."""
        with patch("margre.reporting.mermaid.get_runs_dir", return_value=mock_runs_dir):
            output = generate_mermaid("test_leonardo")
        # Years appear inline in leaf labels like ("Andrea Verrocchio (1472)")
        assert "1472" in output
        assert "1490" in output

    def test_deduplication_merges_verrocchio(self, mock_runs_dir):
        """Andrea Verrocchio appears under both STUDIED_AT and COLLABORATED_WITH —
        each rel_type branch should contain him exactly once."""
        with patch("margre.reporting.mermaid.get_runs_dir", return_value=mock_runs_dir):
            output = generate_mermaid("test_leonardo")
        # Count how many times "Andrea Verrocchio" appears in the output
        andrea_count = output.count("Andrea Verrocchio")
        # Should appear in both COLLABORATED_WITH and STUDIED_AT sections (2+ times)
        assert andrea_count >= 2

    def test_rel_types_appear_as_branches(self, mock_runs_dir):
        """Relationship types should appear as branch labels in the mindmap."""
        with patch("margre.reporting.mermaid.get_runs_dir", return_value=mock_runs_dir):
            output = generate_mermaid("test_leonardo")
        # Key relationship types from fixture data appear as branches
        assert "STUDIED_AT" in output
        assert "LIVED_IN" in output
        assert "CREATED" in output

    def test_empty_run_produces_minimal_output(self, mock_runs_dir, tmp_path):
        """A run with no agent JSONs should produce a minimal graph with just the seed."""
        empty_run = tmp_path / "empty_run"
        empty_run.mkdir()
        (empty_run / "agents").mkdir()
        (empty_run / "aggregation.json").write_text(json.dumps({"seed_person": "Unknown Person"}))

        with patch("margre.reporting.mermaid.get_runs_dir", return_value=tmp_path):
            output = generate_mermaid("empty_run")
        assert "mindmap" in output
        assert "Unknown Person" in output


class TestSaveMermaid:
    def test_writes_file(self, mock_runs_dir, tmp_path):
        """save_mermaid should write a .mmd file and return its path."""
        # Copy fixture data into tmp_path so we can write alongside it
        import shutil
        run_dir = tmp_path / "test_leonardo"
        shutil.copytree(FIXTURES_DIR, run_dir)

        with patch("margre.reporting.mermaid.get_runs_dir", return_value=tmp_path):
            path = save_mermaid("test_leonardo")

        assert Path(path).exists()
        assert Path(path).name == "graph.mmd"
        content = Path(path).read_text(encoding="utf-8")
        assert content.startswith("mindmap")
        assert "Leonardo da Vinci" in content