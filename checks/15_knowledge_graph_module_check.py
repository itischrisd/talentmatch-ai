from __future__ import annotations

from pathlib import Path

from langchain_neo4j import Neo4jGraph

from talentmatch.generation import generate_dataset
from util.common import (
    assert_json_serializable,
    assert_true,
    build_check_context,
    load_settings_from_context,
    print_fail,
    print_ok,
    read_effective_env,
)


def _resolve_cv_pdfs(cv_dir: Path) -> list[Path]:
    if not cv_dir.exists():
        return []
    return sorted([p for p in cv_dir.glob("*.pdf") if p.is_file()])


def _create_neo4j_graph(effective_env: dict[str, str]) -> Neo4jGraph:
    uri = effective_env.get("NEO4J_URI", "").strip()
    username = effective_env.get("NEO4J_USERNAME", "").strip()
    password = effective_env.get("NEO4J_PASSWORD", "").strip()
    database = effective_env.get("NEO4J_DATABASE", "").strip()

    if uri and username and password:
        try:
            if database:
                return Neo4jGraph(url=uri, username=username, password=password, database=database)
            return Neo4jGraph(url=uri, username=username, password=password)
        except TypeError:
            return Neo4jGraph()

    return Neo4jGraph()


def _query_single_int(graph: Neo4jGraph, cypher: str, *, key: str) -> int | None:
    result = graph.query(cypher)
    if not result or not isinstance(result, list):
        return None
    first = result[0]
    if not isinstance(first, dict):
        return None
    value = first.get(key)
    return int(value) if isinstance(value, int) else None


def run() -> int:
    """
    Public contract: validates knowledge_graph public API and performs an end-to-end ingestion into Neo4j.
    :return: process exit code (0 success, 1 failure)
    """
    context = build_check_context(Path(__file__))

    settings = load_settings_from_context(context)
    if settings is None:
        return 1

    env_path = context.repo_root / ".env"
    effective_env = read_effective_env(env_path)

    required_neo4j_env = ["NEO4J_URI", "NEO4J_USERNAME", "NEO4J_PASSWORD"]
    missing_neo4j_env = [k for k in required_neo4j_env if not effective_env.get(k)]
    if missing_neo4j_env:
        print_fail(f"Neo4j env missing: {', '.join(missing_neo4j_env)}")
        return 1
    print_ok("Neo4j env present")

    try:
        import talentmatch.knowledge_graph as kg_module

        exported = set(getattr(kg_module, "__all__", []))
        required = {"ingest_pdf_files"}
        ok = assert_true(required.issubset(exported), ok="knowledge_graph public API __all__ ok",
                         fail="knowledge_graph __all__ missing items")
        if not ok:
            return 1
    except Exception as exc:
        print_fail(f"knowledge_graph module public API check failed: {exc}")
        return 1

    use_cases = getattr(getattr(settings, "llm", None), "use_cases", {}) or {}
    ok = assert_true(
        "graph_transformer" in use_cases,
        ok='LLM use-case "graph_transformer" present',
        fail='LLM use-case "graph_transformer" missing in settings.llm.use_cases',
    )
    if not ok:
        present = ", ".join(sorted(str(k) for k in use_cases.keys()))
        print_fail(f"Available use-cases: {present}")
        return 1

    cv_dir = Path(str(settings.paths.programmers_dir))
    pdfs = _resolve_cv_pdfs(cv_dir)

    if not pdfs:
        try:
            payload = generate_dataset()
            print_ok("generate_dataset() succeeded")
            assert_json_serializable(payload, label="generate_dataset payload")
        except Exception as exc:
            print_fail(f"generate_dataset() failed: {exc}")
            return 1

        pdfs = _resolve_cv_pdfs(cv_dir)

    ok = assert_true(bool(pdfs), ok="CV PDFs present for ingestion", fail=f'No CV PDFs found in "{cv_dir}"')
    if not ok:
        return 1

    try:
        graph = _create_neo4j_graph(effective_env)
        pong = graph.query("RETURN 1 AS one")
        ok = assert_true(bool(pong), ok="Neo4j query succeeded", fail="Neo4j query returned empty result")
        if not ok:
            return 1
    except Exception as exc:
        print_fail(f"Neo4j connection/query failed: {exc}")
        return 1

    try:
        from talentmatch.knowledge_graph import ingest_pdf_files

        result = ingest_pdf_files()
        print_ok("ingest_pdf_files() succeeded")
    except Exception as exc:
        print_fail(f"ingest_pdf_files() failed: {exc}")
        return 1

    failures = 0

    failures += 0 if assert_true(isinstance(result, dict), ok="ingestion result is dict",
                                 fail="ingestion result is not dict") else 1
    failures += 0 if assert_json_serializable(result, label="ingestion result") else 1

    processed = int(result.get("processed_pdfs", 0) or 0)
    nodes = int(result.get("stored_nodes", 0) or 0)

    failures += 0 if assert_true(processed > 0, ok="processed_pdfs > 0", fail="processed_pdfs == 0") else 1
    failures += 0 if assert_true(nodes > 0, ok="stored_nodes > 0", fail="stored_nodes == 0") else 1

    total_nodes = _query_single_int(graph, "MATCH (n) RETURN count(n) AS count", key="count")
    total_rels = _query_single_int(graph, "MATCH ()-[r]->() RETURN count(r) AS count", key="count")

    ok = assert_true(isinstance(total_nodes, int), ok="Neo4j node count query ok", fail="Neo4j node count query failed")
    failures += 0 if ok else 1

    ok = assert_true(isinstance(total_rels, int), ok="Neo4j relationship count query ok",
                     fail="Neo4j relationship count query failed")
    failures += 0 if ok else 1

    if isinstance(total_nodes, int) and isinstance(total_rels, int):
        print_ok(f"Neo4j totals after ingestion: nodes={total_nodes} rels={total_rels}")

    if failures == 0:
        print_ok("Knowledge graph module checks passed")
        return 0

    print_fail(f"Knowledge graph module checks failed: {failures} issue(s)")
    return 1


if __name__ == "__main__":
    raise SystemExit(run())
