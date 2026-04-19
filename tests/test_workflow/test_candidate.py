"""Tests for the candidate_node."""

import pytest
from unittest.mock import patch, MagicMock
from margre.workflow.candidate import candidate_node
from margre.workflow.state import Candidate


class TestCandidateNode:
    """Unit tests for candidate_node."""

    @patch("margre.workflow.candidate.person_exists")
    @patch("margre.workflow.candidate.get_config")
    @patch("margre.workflow.candidate.save_run_metadata")
    def test_returns_candidate_objects(self, mock_save, mock_config, mock_exists):
        """candidate_node should return List[Candidate] not List[str]."""
        mock_exists.return_value = False
        mock_cfg = MagicMock()
        mock_cfg.workflow.max_candidates_per_loop = 3
        mock_config.return_value = mock_cfg

        state = {
            "seed_person": "Leonardo da Vinci",
            "agent_results": [
                {
                    "agent_id": "agent_0_test",
                    "report_path": "/runs/abc123/notes/agent_0_test.md",
                }
            ],
            "discovered_persons": [
                "Verrocchio",
                "Botticelli",
                "Verrocchio",
                "Machiavelli",
            ],
            "master_report": "Some master report",
        }

        result = candidate_node(state)

        gaps = result["suggested_gaps"]
        assert len(gaps) == 3
        assert isinstance(gaps[0], Candidate)
        assert gaps[0].name == "Verrocchio"
        assert gaps[0].score == 2.0  # mentioned twice

    @patch("margre.workflow.candidate.person_exists")
    @patch("margre.workflow.candidate.get_config")
    @patch("margre.workflow.candidate.save_run_metadata")
    def test_filters_existing_persons(self, mock_save, mock_config, mock_exists):
        """Persons already in Neo4j should be excluded."""

        def exists(name):
            return name == "Botticelli"

        mock_exists.side_effect = exists
        mock_cfg = MagicMock()
        mock_cfg.workflow.max_candidates_per_loop = 5
        mock_config.return_value = mock_cfg

        state = {
            "seed_person": "Leonardo da Vinci",
            "agent_results": [
                {
                    "agent_id": "agent_0_test",
                    "report_path": "/runs/abc123/notes/agent_0_test.md",
                }
            ],
            "discovered_persons": ["Verrocchio", "Botticelli", "Machiavelli"],
            "master_report": "Some master report",
        }

        result = candidate_node(state)

        names = [c.name for c in result["suggested_gaps"]]
        assert "Botticelli" not in names
        assert "Verrocchio" in names
        assert "Machiavelli" in names

    @patch("margre.workflow.candidate.person_exists")
    @patch("margre.workflow.candidate.get_config")
    @patch("margre.workflow.candidate.save_run_metadata")
    def test_filters_seed_person(self, mock_save, mock_config, mock_exists):
        """The seed person should not appear as a candidate."""
        mock_exists.return_value = False
        mock_cfg = MagicMock()
        mock_cfg.workflow.max_candidates_per_loop = 5
        mock_config.return_value = mock_cfg

        state = {
            "seed_person": "Leonardo da Vinci",
            "agent_results": [
                {
                    "agent_id": "agent_0_test",
                    "report_path": "/runs/abc123/notes/agent_0_test.md",
                }
            ],
            "discovered_persons": ["Leonardo da Vinci", "Verrocchio", "Botticelli"],
            "master_report": "Some master report",
        }

        result = candidate_node(state)

        names = [c.name for c in result["suggested_gaps"]]
        assert "Leonardo da Vinci" not in names

    @patch("margre.workflow.candidate.person_exists")
    @patch("margre.workflow.candidate.get_config")
    @patch("margre.workflow.candidate.save_run_metadata")
    def test_respects_max_candidates_limit(self, mock_save, mock_config, mock_exists):
        """Should cap candidates at max_candidates_per_loop."""
        mock_exists.return_value = False
        mock_cfg = MagicMock()
        mock_cfg.workflow.max_candidates_per_loop = 2
        mock_config.return_value = mock_cfg

        state = {
            "seed_person": "Leonardo da Vinci",
            "agent_results": [
                {
                    "agent_id": "agent_0_test",
                    "report_path": "/runs/abc123/notes/agent_0_test.md",
                }
            ],
            "discovered_persons": ["A", "B", "C", "D", "E"],
            "master_report": "Some master report",
        }

        result = candidate_node(state)

        assert len(result["suggested_gaps"]) == 2

    @patch("margre.workflow.candidate.person_exists")
    @patch("margre.workflow.candidate.get_config")
    @patch("margre.workflow.candidate.save_run_metadata")
    def test_ranks_by_frequency(self, mock_save, mock_config, mock_exists):
        """Candidates mentioned more often should rank higher."""
        mock_exists.return_value = False
        mock_cfg = MagicMock()
        mock_cfg.workflow.max_candidates_per_loop = 10
        mock_config.return_value = mock_cfg

        state = {
            "seed_person": "Leonardo da Vinci",
            "agent_results": [
                {
                    "agent_id": "agent_0_test",
                    "report_path": "/runs/abc123/notes/agent_0_test.md",
                }
            ],
            "discovered_persons": [
                "LowFreq",
                "HighFreq",
                "HighFreq",
                "HighFreq",
                "MedFreq",
                "MedFreq",
            ],
            "master_report": "Some master report",
        }

        result = candidate_node(state)

        assert result["suggested_gaps"][0].name == "HighFreq"
        assert result["suggested_gaps"][0].score == 3.0
        assert result["suggested_gaps"][1].name == "MedFreq"
        assert result["suggested_gaps"][1].score == 2.0
        assert result["suggested_gaps"][2].name == "LowFreq"
        assert result["suggested_gaps"][2].score == 1.0

    @patch("margre.workflow.candidate.person_exists")
    @patch("margre.workflow.candidate.get_config")
    @patch("margre.workflow.candidate.save_run_metadata")
    def test_case_insensitive_seed_filter(self, mock_save, mock_config, mock_exists):
        """Seed person filter should be case-insensitive."""
        mock_exists.return_value = False
        mock_cfg = MagicMock()
        mock_cfg.workflow.max_candidates_per_loop = 5
        mock_config.return_value = mock_cfg

        state = {
            "seed_person": "leonardo da vinci",
            "agent_results": [
                {
                    "agent_id": "agent_0_test",
                    "report_path": "/runs/abc123/notes/agent_0_test.md",
                }
            ],
            "discovered_persons": ["Leonardo Da Vinci", "Verrocchio"],
            "master_report": "Some master report",
        }

        result = candidate_node(state)

        names = [c.name for c in result["suggested_gaps"]]
        assert "Leonardo Da Vinci" not in names
