"""Tests for the HITL plan revision loop in CLI and planner."""

import json
import pytest
from unittest.mock import patch, MagicMock
from margre.workflow.planner import planner_node
from margre.workflow.state import DiscoveryPlan, DiscoveryTask


class TestRouteAfterPlanner:
    """Unit tests for route_after_planner routing logic."""

    def test_no_plan_yet_routes_to_planner(self):
        from margre.workflow.orchestrator import route_after_planner

        state = {"plan": None, "user_approved_plan": False, "plan_revision_comments": None}
        result = route_after_planner(state)
        assert result == "planner"

    def test_has_plan_no_approval_routes_to_dispatch(self):
        from margre.workflow.orchestrator import route_after_planner

        mock_plan = MagicMock()
        state = {"plan": mock_plan, "user_approved_plan": False, "plan_revision_comments": None}
        result = route_after_planner(state)
        assert result == "researcher_dispatch"

    def test_approved_routes_to_dispatch(self):
        from margre.workflow.orchestrator import route_after_planner

        mock_plan = MagicMock()
        state = {"plan": mock_plan, "user_approved_plan": True, "plan_revision_comments": None}
        result = route_after_planner(state)
        assert result == "researcher_dispatch"

    def test_has_revision_comments_routes_back_to_planner(self):
        from margre.workflow.orchestrator import route_after_planner

        mock_plan = MagicMock()
        state = {
            "plan": mock_plan,
            "user_approved_plan": False,
            "plan_revision_comments": "[2] delete this",
        }
        result = route_after_planner(state)
        assert result == "planner"


class TestFallbackJsonNormalization:
    """Tests for fallback JSON field name normalization in planner_node."""

    @patch("margre.workflow.planner.get_model")
    @patch("margre.workflow.planner.get_person_connections")
    def test_normalizes_search_query_to_research_query(self, mock_connections, mock_get_model):
        """Fallback parser should map search_query → research_query."""
        mock_connections.return_value = []
        mock_model = MagicMock()

        # Structured output path fails to trigger fallback
        mock_structured = MagicMock()
        mock_structured.invoke.side_effect = Exception("structured output failed")

        # Fallback LLM returns JSON with 'search_query' instead of 'research_query'
        fallback_json = json.dumps({
            "seed_person": "Leonardo da Vinci",
            "subtasks": [
                {
                    "target_person": "Leonardo da Vinci",
                    "search_angle": "collaborators",
                    "search_query": "Leonardo da Vinci collaborators",
                }
            ],
        })
        mock_model.with_structured_output.return_value = mock_structured
        mock_model.invoke.return_value = MagicMock(content=f"```json\n{fallback_json}\n```")
        mock_get_model.return_value = mock_model

        state = {
            "seed_person": "Leonardo da Vinci",
            "loop_count": 0,
            "plan_revision_comments": None,
            "plan_revision_count": 0,
        }

        result = planner_node(state)
        assert result["plan"].subtasks[0].research_query == "Leonardo da Vinci collaborators"

    @patch("margre.workflow.planner.get_model")
    @patch("margre.workflow.planner.get_person_connections")
    def test_normalizes_angle_to_search_angle(self, mock_connections, mock_get_model):
        """Fallback parser should map angle → search_angle."""
        mock_connections.return_value = []
        mock_model = MagicMock()

        mock_structured = MagicMock()
        mock_structured.invoke.side_effect = Exception("structured output failed")

        fallback_json = json.dumps({
            "seed_person": "Leonardo da Vinci",
            "subtasks": [
                {
                    "target_person": "Leonardo da Vinci",
                    "angle": "collaborators",
                    "research_query": "Leonardo da Vinci collaborators",
                }
            ],
        })
        mock_model.with_structured_output.return_value = mock_structured
        mock_model.invoke.return_value = MagicMock(content=f"```json\n{fallback_json}\n```")
        mock_get_model.return_value = mock_model

        state = {
            "seed_person": "Leonardo da Vinci",
            "loop_count": 0,
            "plan_revision_comments": None,
            "plan_revision_count": 0,
        }

        result = planner_node(state)
        assert result["plan"].subtasks[0].search_angle == "collaborators"


class TestPlannerNodeRevisionMode:
    """Unit tests for planner_node revision behavior."""

    @patch("margre.workflow.planner.get_model")
    @patch("margre.workflow.planner.get_person_connections")
    def test_revision_mode_uses_structured_output(self, mock_connections, mock_get_model):
        """Revision mode uses structured output like normal planning mode."""
        mock_connections.return_value = []
        mock_model = MagicMock()
        mock_structured = MagicMock()
        mock_structured.invoke.return_value = DiscoveryPlan(
            seed_person="Leonardo da Vinci",
            subtasks=[
                DiscoveryTask(
                    target_person="Leonardo da Vinci",
                    search_angle="friends",
                    research_query="Leonardo da Vinci close friendships",
                ),
                DiscoveryTask(
                    target_person="Leonardo da Vinci",
                    search_angle="collaborators",
                    research_query="Leonardo da Vinci collaborators and associates",
                ),
            ],
        )
        mock_model.with_structured_output.return_value = mock_structured
        mock_get_model.return_value = mock_model

        state = {
            "seed_person": "Leonardo da Vinci",
            "loop_count": 0,
            "plan": DiscoveryPlan(
                seed_person="Leonardo da Vinci",
                subtasks=[
                    DiscoveryTask(
                        target_person="Leonardo da Vinci",
                        search_angle="collaborators",
                        research_query="Leonardo da Vinci collaborators",
                    )
                ],
            ),
            "plan_revision_comments": "[1] change to friends of Leonardo",
            "plan_revision_count": 0,
        }

        result = planner_node(state)

        assert result["plan_revision_count"] == 1
        assert result["plan_revision_comments"] is None
        assert result["plan"].seed_person == "Leonardo da Vinci"
        assert len(result["plan"].subtasks) == 2
        assert result["plan"].subtasks[0].search_angle == "friends"
        # Verify structured output was used (not plain model.invoke)
        mock_structured.invoke.assert_called_once()

    @patch("margre.workflow.planner.get_model")
    @patch("margre.workflow.planner.get_person_connections")
    def test_revision_count_increments_on_each_revision(self, mock_connections, mock_get_model):
        """plan_revision_count increments each time comments are processed."""
        mock_connections.return_value = []
        mock_model = MagicMock()
        mock_structured = MagicMock()
        mock_structured.invoke.return_value = DiscoveryPlan(
            seed_person="Leonardo da Vinci",
            subtasks=[
                DiscoveryTask(
                    target_person="Leonardo da Vinci",
                    search_angle="friends",
                    research_query="Leonardo da Vinci close friendships",
                )
            ],
        )
        mock_model.with_structured_output.return_value = mock_structured
        mock_get_model.return_value = mock_model

        state = {
            "seed_person": "Leonardo da Vinci",
            "loop_count": 1,
            "plan": DiscoveryPlan(
                seed_person="Leonardo da Vinci",
                subtasks=[
                    DiscoveryTask(
                        target_person="Leonardo da Vinci",
                        search_angle="collaborators",
                        research_query="Leonardo da Vinci collaborators",
                    )
                ],
            ),
            "plan_revision_comments": "Add a task for French intellectuals",
            "plan_revision_count": 2,
        }

        result = planner_node(state)

        assert result["plan_revision_count"] == 3

    @patch("margre.workflow.planner.get_model")
    @patch("margre.workflow.planner.get_person_connections")
    def test_no_comments_normal_planning_mode(self, mock_connections, mock_get_model):
        """Normal planning (no comments) uses discovery prompt."""
        mock_connections.return_value = []
        mock_model = MagicMock()
        mock_structured = MagicMock()
        mock_structured.invoke.return_value = DiscoveryPlan(
            seed_person="Leonardo da Vinci",
            subtasks=[
                DiscoveryTask(
                    target_person="Leonardo da Vinci",
                    search_angle="collaborators",
                    research_query="Leonardo da Vinci collaborators and associates",
                )
            ],
        )
        mock_model.with_structured_output.return_value = mock_structured
        mock_get_model.return_value = mock_model

        state = {
            "seed_person": "Leonardo da Vinci",
            "loop_count": 0,
            "plan": None,
            "plan_revision_comments": None,
            "plan_revision_count": 0,
        }

        result = planner_node(state)

        assert result["plan_revision_count"] == 0
        assert result["plan_revision_comments"] is None
        assert result["user_approved_plan"] is False

    @patch("margre.workflow.planner.get_model")
    @patch("margre.workflow.planner.get_person_connections")
    def test_comments_cleared_after_processing(self, mock_connections, mock_get_model):
        """plan_revision_comments is set to None after the planner processes them."""
        mock_connections.return_value = []
        mock_model = MagicMock()
        mock_structured = MagicMock()
        mock_structured.invoke.return_value = DiscoveryPlan(
            seed_person="Leonardo da Vinci",
            subtasks=[
                DiscoveryTask(
                    target_person="Leonardo da Vinci",
                    search_angle="collaborators",
                    research_query="Leonardo da Vinci collaborators",
                )
            ],
        )
        mock_model.with_structured_output.return_value = mock_structured
        mock_get_model.return_value = mock_model

        state = {
            "seed_person": "Leonardo da Vinci",
            "loop_count": 0,
            "plan": DiscoveryPlan(
                seed_person="Leonardo da Vinci",
                subtasks=[
                    DiscoveryTask(
                        target_person="Leonardo da Vinci",
                        search_angle="collaborators",
                        research_query="Leonardo da Vinci collaborators",
                    )
                ],
            ),
            "plan_revision_comments": "delete [1]",
            "plan_revision_count": 0,
        }

        result = planner_node(state)

        assert result["plan_revision_comments"] is None