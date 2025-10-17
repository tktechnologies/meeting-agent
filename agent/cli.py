from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Dict, List, Optional

from . import agenda, db_router as db, retrieval, textgen
from .config import DB_PATH, DEFAULT_ORG_ID
from .nl_parser import parse_nl


def _json_print(payload: Any) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def _row_to_dict(row: Any) -> Dict[str, Any]:
    data = {k: row[k] for k in row.keys()}
    payload = data.get("payload")
    if isinstance(payload, str):
        try:
            data["payload"] = json.loads(payload)
        except Exception:
            data["payload"] = {}
    return data


def cmd_init_db(args: argparse.Namespace) -> None:
    db.init_db()
    ensure_org = args.org or DEFAULT_ORG_ID
    db.ensure_org(ensure_org, args.name or ensure_org)
    print(f"Initialized Spine DB at {DB_PATH} and ensured org '{ensure_org}'.")


def cmd_org_add(args: argparse.Namespace) -> None:
    db.ensure_org(args.org_id, args.name)
    print(f"Org '{args.org_id}' ensured (name='{args.name or args.org_id}').")


def cmd_org_set_context(args: argparse.Namespace) -> None:
    lang = args.language
    db.init_db()
    db.set_org_context(args.org_id, context_text=args.text, language=lang)
    print(json.dumps({"org_id": args.org_id, "language": lang, "updated": True}, ensure_ascii=False))


def cmd_org_show_context(args: argparse.Namespace) -> None:
    db.init_db()
    row = db.get_org_context(args.org_id)
    if not row:
        print(json.dumps({"org_id": args.org_id, "context": None}, ensure_ascii=False))
        return
    out = {k: row[k] for k in row.keys()}
    print(json.dumps(out, ensure_ascii=False, indent=2))


def cmd_context_set(args: argparse.Namespace) -> None:
    db.init_db()
    db.set_global_context(context_text=args.text, language=args.language)
    print(json.dumps({"context_id": "default", "language": args.language, "updated": True}, ensure_ascii=False))


def cmd_context_show(args: argparse.Namespace) -> None:
    db.init_db()
    row = db.get_global_context("default")
    if not row:
        print(json.dumps({"context_id": "default", "context": None}, ensure_ascii=False))
        return
    out = {k: row[k] for k in row.keys()}
    print(json.dumps(out, ensure_ascii=False, indent=2))


def cmd_agenda_propose(args: argparse.Namespace) -> None:
    result = agenda.propose_agenda(
        org=args.org,
        subject=args.subject,
        prompt=args.prompt,
        meeting_id=args.meeting,
        transcript_id=args.transcript,
        duration_minutes=args.duration,
        language=args.language,
    )
    _json_print(result)


def cmd_agenda_list(args: argparse.Namespace) -> None:
    listing = agenda.list_agenda_proposals(args.org, limit=args.limit)
    _json_print(listing)


def cmd_agenda_preview(args: argparse.Namespace) -> None:
    if args.next:
        result = agenda.plan_agenda_next_only(
            org=args.org,
            subject=args.subject,
            company_context=args.context,
            duration_minutes=args.duration,
            language=args.language,
        )
    else:
        result = agenda.plan_agenda_only(
            org=args.org,
            subject=args.subject,
            prompt=args.prompt,
            duration_minutes=args.duration,
            language=args.language,
        )
    if args.nl:
        lang = args.language or "pt-BR"
        prop = result.get("proposal") or {}
        text = textgen.agenda_to_text(
            {"agenda": prop.get("agenda"), "subject": result.get("subject")},
            language=lang,
            use_llm=args.llm,
            with_refs=getattr(args, "with_refs", False),
        )
        if getattr(args, "debug", False):
            sup = (result.get("proposal") or {}).get("supporting_fact_ids") or []
            if sup:
                text += "\n\nEvidence IDs: " + ", ".join(map(str, sup)) + "\n"
        print(text)
    else:
        _json_print(result)


def cmd_agenda_nl(args: argparse.Namespace) -> None:
    # Parse free-text and default to forward-looking agenda with sensible defaults
    text = args.text
    defaults: Dict[str, Any] = {}
    parsed = parse_nl(text, defaults)
    # Resolve org: if none found, ensure DEFAULT_ORG_ID
    org_id = retrieval.resolve_org_id(
        parsed.org_hint or args.org,
        allow_create=False,
        full_text=text,
    )
    minutes = args.duration or parsed.target_duration_minutes or 30
    # Keep parsed.language if provided, else default pt-BR
    lang = args.language or parsed.language or "pt-BR"
    subject = args.subject or parsed.subject  # optional
    # Plan forward-looking agenda; allow override company context via flag
    result = agenda.plan_agenda_next_only(
        org=org_id,
        subject=subject,
        company_context=args.context,
        duration_minutes=minutes,
        language=lang,
    )
    if args.nl:
        prop = result.get("proposal") or {}
        text_out = textgen.agenda_to_text(
            {"agenda": prop.get("agenda"), "subject": result.get("subject")},
            language=lang,
            use_llm=args.llm,
            with_refs=getattr(args, "with_refs", False),
        )
        if getattr(args, "debug", False):
            sup = (result.get("proposal") or {}).get("supporting_fact_ids") or []
            if sup:
                text_out += "\n\nEvidence IDs: " + ", ".join(map(str, sup)) + "\n"
        print(text_out)
    else:
        _json_print(result)


def cmd_agenda_standard(args: argparse.Namespace) -> None:
    if args.next:
        result = agenda.plan_agenda_next_only(
            org=args.org,
            subject=None,
            company_context=args.context,
            duration_minutes=args.duration,
            language=args.language,
        )
    else:
        result = agenda.plan_agenda_only(
            org=args.org,
            subject=None,
            duration_minutes=args.duration,
            language=args.language,
        )
    if args.nl:
        lang = args.language or "pt-BR"
        prop = result.get("proposal") or {}
        text = textgen.agenda_to_text(
            {"agenda": prop.get("agenda"), "subject": result.get("subject")},
            language=lang,
            use_llm=args.llm,
            with_refs=getattr(args, "with_refs", False),
        )
        if getattr(args, "debug", False):
            sup = (result.get("proposal") or {}).get("supporting_fact_ids") or []
            if sup:
                text += "\n\nEvidence IDs: " + ", ".join(map(str, sup)) + "\n"
        print(text)
    else:
        _json_print(result)


def cmd_agenda_subject(args: argparse.Namespace) -> None:
    if args.next:
        result = agenda.plan_agenda_next_only(
            org=args.org,
            subject=args.subject,
            company_context=args.context,
            duration_minutes=args.duration,
            language=args.language,
        )
    else:
        result = agenda.plan_agenda_only(
            org=args.org,
            subject=args.subject,
            duration_minutes=args.duration,
            language=args.language,
        )
    if args.nl:
        lang = args.language or "pt-BR"
        prop = result.get("proposal") or {}
        text = textgen.agenda_to_text(
            {"agenda": prop.get("agenda"), "subject": result.get("subject")},
            language=lang,
            use_llm=args.llm,
            with_refs=getattr(args, "with_refs", False),
        )
        print(text)
    else:
        _json_print(result)


def _parse_types(raw: Optional[str]) -> Optional[List[str]]:
    if not raw:
        return None
    items = [part.strip() for part in raw.split(",")]
    return [item for item in items if item]


def cmd_facts_search(args: argparse.Namespace) -> None:
    org_id = retrieval.resolve_org_id(args.org)
    types = _parse_types(args.types)
    rows = db.search_facts(org_id, args.q or "", types, args.limit)
    payload = {
        "org_id": org_id,
        "query": args.q,
        "types": types,
        "items": [_row_to_dict(row) for row in rows],
    }
    _json_print(payload)


def cmd_facts_status(args: argparse.Namespace) -> None:
    status = args.status.strip().lower()
    try:
        db.update_fact_status(args.fact_id, status)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)
    rows = db.get_fact_rows([args.fact_id])
    if not rows:
        print(f"Fact not found: {args.fact_id}", file=sys.stderr)
        sys.exit(1)
    fact = _row_to_dict(rows[0])
    _json_print({"fact_id": args.fact_id, "status": fact["status"], "updated_at": fact.get("updated_at")})


def cmd_seed_minimal(args: argparse.Namespace) -> None:  # noqa: ARG001 - required signature
    try:
        from scripts.seed import run as seed_run
    except Exception as exc:  # pragma: no cover - optional dependency path issues
        print(f"Unable to import seed script: {exc}", file=sys.stderr)
        sys.exit(1)
    result = seed_run()
    _json_print(result)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Meeting agenda agent CLI")
    parser.set_defaults(func=None)
    sub = parser.add_subparsers(dest="command")

    init_cmd = sub.add_parser("init-db", help="Initialize SQLite Spine DB")
    init_cmd.add_argument("--org", default=DEFAULT_ORG_ID, help="Org id to ensure (default: org_demo)")
    init_cmd.add_argument("--name", default=None, help="Optional org display name")
    init_cmd.set_defaults(func=cmd_init_db)

    org_cmd = sub.add_parser("org", help="Org utilities")
    org_sub = org_cmd.add_subparsers(dest="org_cmd", required=True)
    org_add = org_sub.add_parser("add", help="Insert or update an org")
    org_add.add_argument("org_id", help="Org identifier")
    org_add.add_argument("name", nargs="?", default=None, help="Optional display name")
    org_add.set_defaults(func=cmd_org_add)

    org_ctx_set = org_sub.add_parser("set-context", help="Set/update org context text for agents")
    org_ctx_set.add_argument("org_id", help="Org identifier")
    org_ctx_set.add_argument("text", help="Context text (1-3 sentences recommended)")
    org_ctx_set.add_argument("--language", default=None, help="Language code, e.g., pt-BR")
    org_ctx_set.set_defaults(func=cmd_org_set_context)

    org_ctx_show = org_sub.add_parser("show-context", help="Show org context text")
    org_ctx_show.add_argument("org_id", help="Org identifier")
    org_ctx_show.set_defaults(func=cmd_org_show_context)

    # Global context commands (applies across orgs)
    ctx_cmd = sub.add_parser("context", help="Global context utilities for all orgs")
    ctx_sub = ctx_cmd.add_subparsers(dest="ctx_cmd", required=True)
    ctx_set = ctx_sub.add_parser("set", help="Set/update global context text")
    ctx_set.add_argument("text", help="Context text (rich multi-line supported if quoted)")
    ctx_set.add_argument("--language", default=None, help="Language code, e.g., pt-BR")
    ctx_set.set_defaults(func=cmd_context_set)
    ctx_show = ctx_sub.add_parser("show", help="Show global context text")
    ctx_show.set_defaults(func=cmd_context_show)

    agenda_cmd = sub.add_parser("agenda", help="Agenda workflows")
    agenda_sub = agenda_cmd.add_subparsers(dest="agenda_cmd", required=True)
    agenda_propose = agenda_sub.add_parser("propose", help="Generate and persist a meeting agenda proposal")
    agenda_propose.add_argument("--org", default=None, help="Org id or text hint")
    agenda_propose.add_argument("--subject", default=None, help="Optional meeting subject")
    agenda_propose.add_argument("--prompt", default=None, help="Natural language request to parse")
    agenda_propose.add_argument("--meeting", default=None, help="Optional meeting id")
    agenda_propose.add_argument("--transcript", default=None, help="Optional transcript id")
    agenda_propose.add_argument("--duration", type=int, default=None, help="Target duration (minutes)")
    agenda_propose.add_argument("--language", default=None, help="Language hint (e.g., en-US)")
    agenda_propose.set_defaults(func=cmd_agenda_propose)

    agenda_list = agenda_sub.add_parser("list", help="List recent agenda proposals")
    agenda_list.add_argument("--org", default=None, help="Org id or hint")
    agenda_list.add_argument("--limit", type=int, default=20, help="Maximum results (default 20)")
    agenda_list.set_defaults(func=cmd_agenda_list)

    agenda_preview = agenda_sub.add_parser("preview", help="Plan an agenda without persisting")
    agenda_preview.add_argument("--org", default=None, help="Org id or hint")
    agenda_preview.add_argument("--subject", default=None, help="Optional meeting subject")
    agenda_preview.add_argument("--prompt", default=None, help="Natural language request to parse")
    agenda_preview.add_argument("--duration", type=int, default=None, help="Target duration (minutes)")
    agenda_preview.add_argument("--language", default=None, help="Language hint (e.g., pt-BR)")
    agenda_preview.add_argument("--nl", action="store_true", help="Output in natural language instead of JSON")
    agenda_preview.add_argument("--llm", action="store_true", help="Use LLM to improve text (requires OPENAI_API_KEY)")
    agenda_preview.add_argument("--next", action="store_true", help="Use forward-looking mode (next subjects)")
    agenda_preview.add_argument("--context", default=None, help="Optional company context text")
    agenda_preview.add_argument("--debug", action="store_true", help="Append Evidence IDs to NL output")
    agenda_preview.add_argument("--with-refs", action="store_true", help="Mostrar referências na saída de texto")
    agenda_preview.set_defaults(func=cmd_agenda_preview)

    agenda_standard = agenda_sub.add_parser("standard", help="Plan a standard (no-subject) agenda without persisting")
    agenda_standard.add_argument("--org", default=None, help="Org id or hint")
    agenda_standard.add_argument("--duration", type=int, default=None, help="Target duration (minutes)")
    agenda_standard.add_argument("--language", default=None, help="Language hint (e.g., pt-BR)")
    agenda_standard.add_argument("--nl", action="store_true", help="Output in natural language instead of JSON")
    agenda_standard.add_argument("--llm", action="store_true", help="Use LLM to improve text (requires OPENAI_API_KEY)")
    agenda_standard.add_argument("--next", action="store_true", help="Use forward-looking mode (next subjects)")
    agenda_standard.add_argument("--context", default=None, help="Optional company context text")
    agenda_standard.add_argument("--debug", action="store_true", help="Append Evidence IDs to NL output")
    agenda_standard.add_argument("--with-refs", action="store_true", help="Mostrar referências na saída de texto")
    agenda_standard.set_defaults(func=cmd_agenda_standard)

    agenda_subject = agenda_sub.add_parser("subject", help="Plan a subject-focused agenda without persisting")
    agenda_subject.add_argument("--org", default=None, help="Org id or hint")
    agenda_subject.add_argument("subject", help="Subject text to focus the agenda on")
    agenda_subject.add_argument("--duration", type=int, default=None, help="Target duration (minutes)")
    agenda_subject.add_argument("--language", default=None, help="Language hint (e.g., pt-BR)")
    agenda_subject.add_argument("--nl", action="store_true", help="Output in natural language instead of JSON")
    agenda_subject.add_argument("--llm", action="store_true", help="Use LLM to improve text (requires OPENAI_API_KEY)")
    agenda_subject.add_argument("--next", action="store_true", help="Use forward-looking mode (next subjects)")
    agenda_subject.add_argument("--context", default=None, help="Optional company context text")
    agenda_subject.add_argument("--with-refs", action="store_true", help="Mostrar referências na saída de texto")
    agenda_subject.set_defaults(func=cmd_agenda_subject)

    agenda_nl = agenda_sub.add_parser("nl", help="Natural language entrypoint for agenda planning (forward-looking by default)")
    agenda_nl.add_argument("text", help="User request, e.g., 'faça a pauta da minha próxima reunião com a BYD'")
    agenda_nl.add_argument("--org", default=None, help="Fallback org id or hint if NL parse fails")
    agenda_nl.add_argument("--subject", default=None, help="Optional subject override")
    agenda_nl.add_argument("--duration", type=int, default=None, help="Target duration (minutes); defaults to 30")
    agenda_nl.add_argument("--language", default=None, help="Language hint (e.g., pt-BR)")
    agenda_nl.add_argument("--context", default=None, help="Optional company context override")
    agenda_nl.add_argument("--nl", action="store_true", help="Output in natural language instead of JSON")
    agenda_nl.add_argument("--llm", action="store_true", help="Use LLM to improve text (requires OPENAI_API_KEY)")
    agenda_nl.add_argument("--debug", action="store_true", help="Append Evidence IDs to NL output")
    agenda_nl.add_argument("--with-refs", action="store_true", help="Mostrar referências na saída de texto")
    agenda_nl.set_defaults(func=cmd_agenda_nl)

    facts_cmd = sub.add_parser("facts", help="Facts utilities")
    facts_sub = facts_cmd.add_subparsers(dest="facts_cmd", required=True)
    facts_search = facts_sub.add_parser("search", help="Search facts via FTS")
    facts_search.add_argument("--org", default=None, help="Org id or hint")
    facts_search.add_argument("--q", default=None, help="Search query")
    facts_search.add_argument("--types", default=None, help="Comma-separated fact types filter")
    facts_search.add_argument("--limit", type=int, default=50, help="Maximum results (default 50)")
    facts_search.set_defaults(func=cmd_facts_search)

    facts_status = facts_sub.add_parser("set-status", help="Update a fact status")
    facts_status.add_argument("fact_id", help="Fact identifier")
    facts_status.add_argument("status", help="New status (draft|proposed|validated|published|rejected)")
    facts_status.set_defaults(func=cmd_facts_status)

    seed_cmd = sub.add_parser("seed", help="Seeding helpers")
    seed_sub = seed_cmd.add_subparsers(dest="seed_cmd", required=True)
    seed_min = seed_sub.add_parser("minimal", help="Load demo facts into the DB")
    seed_min.set_defaults(func=cmd_seed_minimal)

    return parser


def main(argv: Optional[List[str]] = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "func", None):
        parser.print_help()
        parser.exit(2)
    args.func(args)


if __name__ == "__main__":
    main()
