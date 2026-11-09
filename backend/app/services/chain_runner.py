"""Multi-agent chain orchestration.

A chain is a DAG of steps, each bound to an agent. Steps are grouped into
topological levels; every level runs concurrently with `asyncio.gather`, and
each step receives its upstream steps' outputs as its user message.
"""

import asyncio
import time
from collections.abc import Mapping

from app.core.logging import get_logger
from app.models.agent import AgentPublic
from app.models.chain import ChainPublic, ChainRunResult, StepTrace
from app.models.common import new_id, utcnow
from app.services.agent_executor import AgentRuntime
from app.utils.graph import resolve_dependencies, sink_nodes, topological_levels

logger = get_logger(__name__)


def build_step_input(chain_input: str, deps: list[str], outputs: Mapping[str, str]) -> str:
    """Compose a step's user message from the chain input or upstream outputs."""
    if not deps:
        return chain_input
    if len(deps) == 1:
        return outputs[deps[0]]
    sections = "\n\n".join(f"### Output from step `{dep}`\n{outputs[dep]}" for dep in deps)
    return f"Original request:\n{chain_input}\n\n{sections}"


def combine_final_output(sinks: list[str], outputs: Mapping[str, str]) -> str:
    available = [s for s in sinks if s in outputs]
    if len(available) == 1:
        return outputs[available[0]]
    return "\n\n".join(f"### {s}\n{outputs[s]}" for s in available)


class ChainRunner:
    def __init__(self, runtime: AgentRuntime) -> None:
        self._runtime = runtime

    async def _run_step(
        self,
        *,
        step_id: str,
        agent: AgentPublic,
        level: int,
        deps: list[str],
        step_input: str,
    ) -> StepTrace:
        started_at = utcnow()
        start = time.perf_counter()
        try:
            result = await self._runtime.run(agent, step_input)
            status, output, error, tool_calls = "success", result.output, None, result.tool_calls
        except Exception as exc:
            logger.warning("chain_step_failed", step_id=step_id, agent_id=agent.id, error=str(exc))
            status, output, error, tool_calls = "error", None, f"{type(exc).__name__}: {exc}"[:500], []
        return StepTrace(
            step_id=step_id,
            agent_id=agent.id,
            agent_name=agent.name,
            level=level,
            depends_on=deps,
            input=step_input,
            output=output,
            tool_calls=tool_calls,
            status=status,
            error=error,
            started_at=started_at,
            finished_at=utcnow(),
            duration_ms=round((time.perf_counter() - start) * 1000, 1),
        )

    async def run(self, chain: ChainPublic, agents: Mapping[str, AgentPublic], chain_input: str) -> ChainRunResult:
        """Execute the chain and return a full trace with per-step timing."""
        run_started = time.perf_counter()
        created_at = utcnow()
        steps_by_id = {s.id: s for s in chain.steps}
        graph = resolve_dependencies([(s.id, s.depends_on) for s in chain.steps])
        levels = topological_levels(graph)

        outputs: dict[str, str] = {}
        traces: dict[str, StepTrace] = {}

        for level_index, level in enumerate(levels):
            runnable: list[str] = []
            for step_id in level:
                deps = graph[step_id]
                if any(dep not in outputs for dep in deps):
                    now = utcnow()
                    agent = agents[steps_by_id[step_id].agent_id]
                    traces[step_id] = StepTrace(
                        step_id=step_id, agent_id=agent.id, agent_name=agent.name, level=level_index,
                        depends_on=deps, input="", status="skipped",
                        error="Skipped because an upstream step failed",
                        started_at=now, finished_at=now, duration_ms=0.0,
                    )
                else:
                    runnable.append(step_id)

            results = await asyncio.gather(
                *(
                    self._run_step(
                        step_id=step_id,
                        agent=agents[steps_by_id[step_id].agent_id],
                        level=level_index,
                        deps=graph[step_id],
                        step_input=build_step_input(chain_input, graph[step_id], outputs),
                    )
                    for step_id in runnable
                )
            )
            for trace in results:
                traces[trace.step_id] = trace
                if trace.status == "success" and trace.output is not None:
                    outputs[trace.step_id] = trace.output

        ordered = [traces[s.id] for s in chain.steps]
        succeeded = sum(t.status == "success" for t in ordered)
        status = "success" if succeeded == len(ordered) else ("error" if succeeded == 0 else "partial")
        return ChainRunResult(
            id=new_id(),
            chain_id=chain.id,
            owner_id=chain.owner_id,
            input=chain_input,
            final_output=combine_final_output(sink_nodes(graph), outputs),
            status=status,
            steps=ordered,
            total_duration_ms=round((time.perf_counter() - run_started) * 1000, 1),
            created_at=created_at,
        )
