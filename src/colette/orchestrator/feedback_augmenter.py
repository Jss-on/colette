"""Feedback augmenter — enrich agent prompts with rework context (Phase 2)."""

from __future__ import annotations

from colette.schemas.rework import ReworkDirective


class FeedbackAugmenter:
    """Enriches agent system prompts with failure context from rework directives."""

    def augment_prompt(
        self,
        base_prompt: str,
        rework_directive: ReworkDirective | None,
        previous_attempt_output: dict[str, object] | None,
    ) -> str:
        """Append rework context to *base_prompt* when a directive is active.

        Returns the original prompt unchanged when there is no rework context.
        """
        if rework_directive is None:
            return base_prompt

        sections: list[str] = [base_prompt, "", "## Prior Attempt Context"]

        sections.append(
            f"This is rework attempt {rework_directive.attempt_number}"
            f" of {rework_directive.max_attempts}."
        )
        sections.append(
            f"Source gate: {rework_directive.source_gate} | "
            f"Target stage: {rework_directive.target_stage}"
        )

        if rework_directive.failure_reasons:
            sections.append("\n### Failure Reasons")
            for reason in rework_directive.failure_reasons:
                sections.append(f"- {reason}")

        if rework_directive.human_feedback:
            sections.append("\n### Human Feedback")
            sections.append(rework_directive.human_feedback)

        if rework_directive.modifications:
            sections.append("\n### Requested Modifications")
            for key, value in rework_directive.modifications.items():
                sections.append(f"- **{key}**: {value}")

        if previous_attempt_output:
            sections.append("\n### Previous Attempt Output (summary)")
            for prev_key, prev_val in previous_attempt_output.items():
                val_str = str(prev_val)[:500]
                sections.append(f"- **{prev_key}**: {val_str}")

        if rework_directive.preserved_handoffs:
            sections.append("\n### Preserved Handoffs")
            sections.append(
                "The following prior handoffs are still valid and should be respected:"
            )
            for stage, handoff in rework_directive.preserved_handoffs.items():
                sections.append(f"- **{stage}**: {list(handoff.keys())}")

        sections.append(
            "\n**Focus on addressing the failure reasons above. Do not repeat the same mistakes.**"
        )

        return "\n".join(sections)
