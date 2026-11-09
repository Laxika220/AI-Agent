import pytest

from app.models.chain import ChainCreate
from app.services.chain_runner import build_step_input, combine_final_output
from app.utils.graph import resolve_dependencies, sink_nodes, topological_levels


def test_sequential_chain_defaults_to_previous_step() -> None:
    graph = resolve_dependencies([("a", None), ("b", None), ("c", None)])
    assert graph == {"a": [], "b": ["a"], "c": ["b"]}
    assert topological_levels(graph) == [["a"], ["b"], ["c"]]
    assert sink_nodes(graph) == ["c"]


def test_fan_out_fan_in_runs_independent_steps_in_parallel() -> None:
    graph = resolve_dependencies(
        [("research", []), ("facts", []), ("write", ["research", "facts"]), ("edit", None)]
    )
    assert topological_levels(graph) == [["research", "facts"], ["write"], ["edit"]]


def test_cycle_is_rejected() -> None:
    with pytest.raises(ValueError, match="cycle"):
        topological_levels({"a": ["b"], "b": ["a"]})


def test_unknown_dependency_is_rejected() -> None:
    with pytest.raises(ValueError, match="unknown"):
        topological_levels({"a": ["ghost"]})


def test_chain_schema_validates_graph() -> None:
    with pytest.raises(ValueError):
        ChainCreate(name="bad", steps=[{"id": "a", "agent_id": "x", "depends_on": ["a"]}])
    with pytest.raises(ValueError):
        ChainCreate(name="dupe", steps=[{"id": "a", "agent_id": "x"}, {"id": "a", "agent_id": "y"}])


def test_step_input_composition() -> None:
    outputs = {"a": "alpha", "b": "beta"}
    assert build_step_input("question", [], outputs) == "question"
    assert build_step_input("question", ["a"], outputs) == "alpha"
    merged = build_step_input("question", ["a", "b"], outputs)
    assert "question" in merged and "alpha" in merged and "beta" in merged


def test_final_output_combines_sinks() -> None:
    assert combine_final_output(["a"], {"a": "x"}) == "x"
    combined = combine_final_output(["a", "b"], {"a": "x", "b": "y"})
    assert "x" in combined and "y" in combined
