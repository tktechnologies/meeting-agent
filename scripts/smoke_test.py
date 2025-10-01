from __future__ import annotations

from agent import agenda, textgen, nl_parser, retrieval, db


def main() -> None:
    text = "pauta para próxima reunião com a BYD, 30 min"
    defaults = {}
    parsed = nl_parser.parse_nl(text, defaults)
    org_id = retrieval.resolve_org_id(parsed.org_hint)
    lang = parsed.language or "pt-BR"
    minutes = parsed.target_duration_minutes or 30
    result = agenda.plan_agenda_next_only(
        org=org_id,
        subject=parsed.subject,
        duration_minutes=minutes,
        language=lang,
    )
    prop = result.get("proposal") or {}
    # Simulate CLI and API render calls
    cli_text = textgen.agenda_to_text({"agenda": prop.get("agenda"), "subject": result.get("subject")}, language=lang, with_refs=False)
    api_text = textgen.agenda_to_text({"agenda": prop.get("agenda"), "subject": result.get("subject")}, language=lang, with_refs=False)

    print("=== CLI/API equality:", cli_text == api_text)
    print(cli_text)

    # Fallback check: candidates for agenda
    types = ["decision", "open_question", "risk", "process_step", "action_item", "metric", "milestone"]
    cands = retrieval.find_candidates_for_agenda(org_id, parsed.subject, types, limit=20)
    total = len(cands)
    statuses = {}
    for c in cands:
        st = (c.get("status") or "").lower()
        statuses[st] = statuses.get(st, 0) + 1
    print({"total": total, "status_counts": statuses})
    # Subject-specific facts retrieval
    if parsed.subject:
        rows = retrieval.retrieve_facts_for_subject(org_id, parsed.subject, limit=20, language=lang)
        total2 = len(rows)
        statuses2 = {}
        for r in rows:
            st = (r.get("status") or "").lower()
            statuses2[st] = statuses2.get(st, 0) + 1
        print({"subject_rows": total2, "status_counts_subject": statuses2})


if __name__ == "__main__":
    main()
