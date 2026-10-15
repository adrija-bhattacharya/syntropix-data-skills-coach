"""Practice task content for every domain beyond the core SQL tasks."""

from __future__ import annotations

from practice.tasks import Distractor, Task


def D(value: str, concept: str, code: str, message: str) -> Distractor:
    return Distractor(value, concept, code, message)


def choice(
    id_: str,
    concept: str,
    domain: str,
    prompt: str,
    answer: str,
    wrong: list[tuple[str, str, str, str]],
    *,
    hint: str = "",
    hint2: str = "",
    context: tuple[tuple[str, ...], ...] = (),
    note: str = "",
) -> Task:
    """A pick-one task. ``wrong`` = (option, concept it points to, code, message)."""
    options = (answer, *(w[0] for w in wrong))
    return Task(
        id=id_,
        concept=concept,
        prompt=prompt,
        reference=answer,
        kind="value",
        domain=domain,
        options=options,
        distractors=tuple(D(*w) for w in wrong),
        hint=hint,
        hint2=hint2,
        context=context,
        context_note=note,
    )


def number(
    id_: str,
    concept: str,
    domain: str,
    prompt: str,
    answer: float,
    *,
    tol: float = 0.0,
    wrong: list[tuple[float, str, str, str]] | None = None,
    hint: str = "",
    hint2: str = "",
    context: tuple[tuple[str, ...], ...] = (),
    note: str = "",
) -> Task:
    """A compute-the-number task. ``wrong`` = (value a mistake gives, concept, code, message)."""
    return Task(
        id=id_,
        concept=concept,
        prompt=prompt,
        reference=_fmt(answer),
        kind="value",
        domain=domain,
        tolerance=tol,
        distractors=tuple(D(_fmt(v), c, k, m) for v, c, k, m in (wrong or [])),
        hint=hint,
        hint2=hint2,
        context=context,
        context_note=note,
    )


def _fmt(v: float) -> str:
    return str(int(v)) if float(v).is_integer() else repr(round(float(v), 6))
