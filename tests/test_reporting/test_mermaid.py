"""Tests for Mermaid flowchart generation."""

import json
import re
import pytest
from pathlib import Path
from unittest.mock import patch

from margre.reporting.mermaid import (
    _mermaid_id,
    _mermaid_label,
    _edge_label,
    _deduplicate_relationships,
    generate_mermaid,
    save_mermaid,
    NODE_SHAPES,
    DEFAULT_SHAPE,
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
        assert _mermaid_label("He said \"hello\"") == "He said &#quot;hello&#quot;"

    def test_with_extra(self):
        result = _mermaid_label("Milan", "city")
        assert "Milan" in result
        assert "<br/>" in result


class TestEdgeLabel:
    def test_type_only(self):
        assert _edge_label("KNEW", None, None) == "KNEW"

    def test_type_with_year(self):
        assert _edge_label("COLLABORATED_WITH", 1490, None) == "COLLABORATED_WITH 1490"

    def test_type_with_period_no_year(self):
        assert _edge_label("INFLUENCED", None, "1490s") == "INFLUENCED 1490s"

    def test_year_takes_precedence_over_period(self):
        assert _edge_label("KNEW", 1500, "Early 16th century") == "KNEW 1500"


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
        assert output.startswith("graph LR\n")

    def test_seed_person_declared_first(self, mock_runs_dir):
        with patch("margre.reporting.mermaid.get_runs_dir", return_value=mock_runs_dir):
            output = generate_mermaid("test_leonardo")
        lines = output.strip().split("\n")
        # First line is "graph LR", second should be seed person node
        assert "Leonardo_da_Vinci" in lines[1]
        assert "Leonardo da Vinci" in lines[1]

    def test_no_self_edge(self, mock_runs_dir):
        """Seed person should not have an edge pointing to itself."""
        with patch("margre.reporting.mermaid.get_runs_dir", return_value=mock_runs_dir):
            output = generate_mermaid("test_leonardo")
        for line in output.split("\n"):
            if "Leonardo_da_Vinci -->|" in line:
                # The target (after |) should not be Leonardo_da_Vinci again
                assert line.rstrip().endswith("Leonardo_da_Vinci") is False, \
                    f"Self-edge found: {line}"

    def test_different_node_shapes(self, mock_runs_dir):
        """Different entity labels should use different Mermaid shapes."""
        with patch("margre.reporting.mermaid.get_runs_dir", return_value=mock_runs_dir):
            output = generate_mermaid("test_leonardo")

        # Location (Milan) should use {{ }}
        assert "Milan{{" in output or "Milan}}{{" in output or '{{"Milan"}}' in output

        # Institution (Verrocchio's Workshop) should use [ ]
        assert "Verrocchio_s_Workshop[" in output

        # Contribution (The Last Supper) should use [[ ]]
        assert "[[" in output  # Double bracket for Contribution shape

    def test_edge_labels_include_year(self, mock_runs_dir):
        """Edges should show rel_type and year."""
        with patch("margre.reporting.mermaid.get_runs_dir", return_value=mock_runs_dir):
            output = generate_mermaid("test_leonardo")
        assert "STUDIED_AT 1472" in output
        assert "COLLABORATED_WITH 1490" in output

    def test_deduplication_merges_verrocchio(self, mock_runs_dir):
        """Andrea Verrocchio appears in both agents with STUDIED_AT and COLLABORATED_WITH —
        deduplication should keep both types but merge duplicates within same type."""
        with patch("margre.reporting.mermaid.get_runs_dir", return_value=mock_runs_dir):
            output = generate_mermaid("test_leonardo")
        # Count edges targeting Andrea Verrocchio specifically (not the Workshop)
        andrea_edges = [l for l in output.split("\n") if "Andrea_Verrocchio" in l and "-->" in l]
        # Two distinct relationship types to the person: STUDIED_AT and COLLABORATED_WITH
        assert len(andrea_edges) == 2

    def test_all_targets_declared_as_nodes(self, mock_runs_dir):
        """Every target in an edge should also have a node declaration."""
        with patch("margre.reporting.mermaid.get_runs_dir", return_value=mock_runs_dir):
            output = generate_mermaid("test_leonardo")

        lines = output.strip().split("\n")

        # Extract node IDs from node declaration lines using regex.
        # Node lines match pattern: <whitespace>NodeID<shape_chars>"Label"<shape_chars>
        # The ID is always the first word (alphanumeric + underscore characters).
        node_id_pattern = re.compile(r'^\s+(\w+)')
        declared_ids = set()
        for line in lines:
            if "-->" in line or line.startswith("graph"):
                continue
            m = node_id_pattern.match(line)
            if m:
                declared_ids.add(m.group(1))

        # Extract target IDs from edge lines
        # Edge lines look like: Seed_ID -->|"label"| Target_ID
        edge_pattern = re.compile(r'-->\|"[^"]*"\|\s*(\w+)')
        for line in lines:
            if "-->" not in line:
                continue
            m = edge_pattern.search(line)
            if m:
                assert m.group(1) in declared_ids or m.group(1) == "Leonardo_da_Vinci", \
                    f"Edge target '{m.group(1)}' has no node declaration"

    def test_empty_run_produces_minimal_output(self, mock_runs_dir, tmp_path):
        """A run with no agent JSONs should produce a minimal graph with just the seed."""
        empty_run = tmp_path / "empty_run"
        empty_run.mkdir()
        (empty_run / "agents").mkdir()
        (empty_run / "aggregation.json").write_text(json.dumps({"seed_person": "Unknown Person"}))

        with patch("margre.reporting.mermaid.get_runs_dir", return_value=tmp_path):
            output = generate_mermaid("empty_run")
        assert "graph LR" in output
        assert "Unknown_Person" in output
        # No edges
        assert "-->" not in output


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
        assert content.startswith("graph LR")
        assert "Leonardo_da_Vinci" in content