"""Dependency-graph helpers for multi-agent chains (pure functions, easy to test)."""

from collections.abc import Sequence


def resolve_dependencies(steps: Sequence[tuple[str, list[str] | None]]) -> dict[str, list[str]]:
    """Turn declared dependencies into an explicit adjacency map.

    `None` means "depends on the previous step" so a plain list of steps behaves
    like a sequential pipeline; the first step then depends on nothing.
    """
    resolved: dict[str, list[str]] = {}
    previous: str | None = None
    for step_id, deps in steps:
        if deps is None:
            resolved[step_id] = [previous] if previous is not None else []
        else:
            resolved[step_id] = list(dict.fromkeys(deps))
        previous = step_id
    return resolved


def topological_levels(graph: dict[str, list[str]]) -> list[list[str]]:
    """Group steps into execution levels (Kahn's algorithm).

    Every step in level N depends only on steps in levels < N, so all steps of a
    level can run concurrently. Order inside a level follows declaration order.

    Raises:
        ValueError: on unknown dependencies, self-dependencies or cycles.
    """
    for node, deps in graph.items():
        for dep in deps:
            if dep not in graph:
                raise ValueError(f"Step '{node}' depends on unknown step '{dep}'")
            if dep == node:
                raise ValueError(f"Step '{node}' cannot depend on itself")

    remaining = {node: set(deps) for node, deps in graph.items()}
    done: set[str] = set()
    levels: list[list[str]] = []
    while remaining:
        ready = [node for node, deps in remaining.items() if deps <= done]
        if not ready:
            raise ValueError(f"Chain contains a dependency cycle among: {sorted(remaining)}")
        levels.append(ready)
        done.update(ready)
        for node in ready:
            del remaining[node]
    return levels


def sink_nodes(graph: dict[str, list[str]]) -> list[str]:
    """Steps no other step depends on — their outputs form the chain's final output."""
    depended_on = {dep for deps in graph.values() for dep in deps}
    return [node for node in graph if node not in depended_on]
