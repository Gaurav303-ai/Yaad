"""Compare newly extracted decisions with prior decision memory."""

import json
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
from supabase import AsyncClient

from app.agents.memory import find_related_decisions, update_memory
from app.core.llm import request_json
from app.core.schemas import Conflict, Decision


class _ConflictAssessment(BaseModel):
    """Strict LLM comparison result, including an explicit no-conflict outcome."""

    model_config = ConfigDict(extra="forbid")

    label: Literal["contradiction", "update", "duplicate", "none"]
    explanation: str = Field(min_length=1)


async def compare_decisions(new: Decision, old: Decision) -> _ConflictAssessment:
    """Classify a related decision pair and explain the relationship."""
    prompt = f"""
Compare a new meeting decision with an earlier active decision.
Return label `none` when they concern different topics or are compatible.
Return `duplicate` when they restate the same commitment without changing it.
Return `update` only when the new quote explicitly revises the earlier decision.
Return `contradiction` when both cannot be true, including a changed committed deadline
without an explicit revision phrase. A later payment date due to cash-flow constraints
is a contradiction; an explicitly moved launch date or recurring meeting schedule is an update.
Do not treat intent, tentative wording, or a restriction on a topic as a conflict with
an earlier intent.
Return a JSON object matching this exact schema and use the `explanation` field name:
{json.dumps(_ConflictAssessment.model_json_schema(), ensure_ascii=False)}

New decision:
{json.dumps(new.model_dump(mode="json"), ensure_ascii=False)}

Earlier decision:
{json.dumps(old.model_dump(mode="json"), ensure_ascii=False)}
""".strip()
    return await request_json(_ConflictAssessment, prompt)


async def detect_conflicts(
    supabase: AsyncClient,
    new_item_id: UUID,
    decision: Decision,
) -> list[Conflict]:
    """Compare, persist, and return conflicts before adding the new decision to memory."""
    if decision.meeting_id is None:
        raise ValueError("A meeting ID is required before conflicts can be checked.")

    earlier_decisions = await find_related_decisions(supabase, decision)
    assessments = [
        (earlier, await compare_decisions(decision, earlier))
        for earlier in earlier_decisions
    ]
    persisted_decision = await update_memory(supabase, decision)
    if persisted_decision.id is None:
        raise RuntimeError("The saved decision is missing its generated ID.")

    conflicts: list[Conflict] = []
    for earlier, assessment in assessments:
        if earlier.id is None:
            raise RuntimeError("A decision retrieved from memory is missing its ID.")
        if assessment.label == "none":
            continue
        values = {
            "new_item_id": str(new_item_id),
            "old_decision_id": str(earlier.id),
            "label": assessment.label,
            "explanation": assessment.explanation,
        }
        response = await supabase.table("conflicts").insert(values).execute()
        if len(response.data) != 1:
            raise RuntimeError("Supabase did not return the saved conflict.")
        conflicts.append(
            Conflict(
                new_item_id=new_item_id,
                old_decision_id=earlier.id,
                label=assessment.label,
                explanation=assessment.explanation,
            )
        )
    return conflicts
