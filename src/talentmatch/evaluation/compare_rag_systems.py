from __future__ import annotations

import argparse
import json
import logging
import re
from dataclasses import asdict, dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Final, Literal

from talentmatch.config import load_settings
from talentmatch.infra.logging import configure_logging
from talentmatch.knowledge_graph import query_knowledge_graph
from talentmatch.knowledge_graph.neo4j import Neo4jGraphService
from talentmatch.vector_store import query_vector_store

logger = logging.getLogger(__name__)

QuestionType = Literal["count", "float", "list"]


@dataclass(frozen=True, slots=True)
class GroundTruth:
    question_type: QuestionType
    canonical: Any
    cypher: str
    parameters: dict[str, Any]


@dataclass(frozen=True, slots=True)
class EvalCase:
    case_id: str
    question: str
    ground_truth: GroundTruth


@dataclass(frozen=True, slots=True)
class SystemAnswer:
    system: str
    answer: str
    reasoning: str
    raw: dict[str, Any]
    elapsed_s: float


@dataclass(frozen=True, slots=True)
class CaseResult:
    case: EvalCase
    truth: GroundTruth
    graphrag: SystemAnswer
    vector_rag: SystemAnswer
    scores: dict[str, Any]


class GroundTruthSuite:
    """
    Builds evaluation questions and their deterministic ground truth using direct Neo4j queries.
    """

    _DEFAULT_TOP_SKILLS: Final[int] = 10
    _DEFAULT_TOP_TECH: Final[int] = 10

    def __init__(self, graph_service: Neo4jGraphService) -> None:
        self._graph_service = graph_service

    def build(self) -> list[EvalCase]:
        skill_id = self._pick_skill_id()
        tech_id = self._pick_technology_id()

        cases: list[EvalCase] = [
            self._count_people_with_skill(skill_id),
            self._list_top_people_by_skill_count(limit=3),
            self._avg_skills_per_person(),
        ]

        if tech_id:
            cases.append(self._count_companies_using_technology(tech_id))

        cases.append(self._count_available_people_on(date.today().isoformat()))

        return cases

    def _pick_skill_id(self) -> str:
        rows = self._graph_service.graph.query(
            """
            MATCH (s:Skill)<-[:HAS_SKILL]-(:Person)
            WITH s, count(*) AS cnt
            ORDER BY cnt DESC, s.id ASC
            LIMIT $limit
            RETURN s.id AS skill_id
            """,
            {"limit": self._DEFAULT_TOP_SKILLS},
        )
        for row in rows or []:
            skill_id = str(row.get("skill_id") or "").strip()
            if skill_id:
                return skill_id
        return "Python"

    def _pick_technology_id(self) -> str | None:
        rows = self._graph_service.graph.query(
            """
            MATCH (t:Technology)<-[:USED_TECHNOLOGY]-(:Project)
            WITH t, count(*) AS cnt
            ORDER BY cnt DESC, t.id ASC
            LIMIT $limit
            RETURN t.id AS tech_id
            """,
            {"limit": self._DEFAULT_TOP_TECH},
        )
        for row in rows or []:
            tech_id = str(row.get("tech_id") or "").strip()
            if tech_id:
                return tech_id
        return None

    @staticmethod
    def _normalize_skill(skill_id: str) -> str:
        return str(skill_id).strip()

    def _count_people_with_skill(self, skill_id: str) -> EvalCase:
        normalized = self._normalize_skill(skill_id)
        question = f"How many programmers have the skill {normalized}?"
        cypher = """
        MATCH (p:Person)-[:HAS_SKILL]->(s:Skill {id: $skill_id})
        RETURN count(DISTINCT p) AS value
        """
        params = {"skill_id": normalized}
        value = self._scalar_int(cypher, params)
        truth = GroundTruth(question_type="count", canonical=value, cypher=cypher.strip(), parameters=params)
        return EvalCase(case_id="count_people_with_skill", question=question, ground_truth=truth)

    def _list_top_people_by_skill_count(self, *, limit: int) -> EvalCase:
        question = f"List the top {limit} programmers by number of skills."
        cypher = """
        MATCH (p:Person)
        OPTIONAL MATCH (p)-[:HAS_SKILL]->(s:Skill)
        WITH p, count(DISTINCT s) AS skill_count
        RETURN coalesce(p.name, p.full_name, p.id) AS name, skill_count
        ORDER BY skill_count DESC, name ASC
        LIMIT $limit
        """
        params = {"limit": int(limit)}
        rows = self._graph_service.graph.query(cypher, params) or []
        names = [str(r.get("name") or "").strip() for r in rows if str(r.get("name") or "").strip()]
        truth = GroundTruth(question_type="list", canonical=names, cypher=cypher.strip(), parameters=params)
        return EvalCase(case_id="top_people_by_skill_count", question=question, ground_truth=truth)

    def _avg_skills_per_person(self) -> EvalCase:
        question = "What is the average number of skills per programmer?"
        cypher = """
        MATCH (p:Person)
        OPTIONAL MATCH (p)-[:HAS_SKILL]->(s:Skill)
        WITH p, count(DISTINCT s) AS skill_count
        RETURN avg(skill_count) AS value
        """
        params: dict[str, Any] = {}
        value = self._scalar_float(cypher, params)
        truth = GroundTruth(question_type="float", canonical=value, cypher=cypher.strip(), parameters=params)
        return EvalCase(case_id="avg_skills_per_person", question=question, ground_truth=truth)

    def _count_companies_using_technology(self, tech_id: str) -> EvalCase:
        normalized = str(tech_id).strip()
        question = f"How many companies have projects that used the technology {normalized}?"
        cypher = """
        MATCH (c:Company)<-[:FOR_COMPANY]-(p:Project)-[:USED_TECHNOLOGY]->(t:Technology {id: $tech_id})
        RETURN count(DISTINCT c) AS value
        """
        params = {"tech_id": normalized}
        value = self._scalar_int(cypher, params)
        truth = GroundTruth(question_type="count", canonical=value, cypher=cypher.strip(), parameters=params)
        return EvalCase(case_id="count_companies_using_technology", question=question, ground_truth=truth)

    def _count_available_people_on(self, date_iso: str) -> EvalCase:
        question = f"How many programmers are available on {date_iso}?"
        cypher = """
        MATCH (p:Person)
        OPTIONAL MATCH (p)-[a:ASSIGNED_TO]->(:Project)
        WHERE
          coalesce(a.start_date, a.assignment_start_date) <= $date_iso
          AND coalesce(a.end_date, a.assignment_end_date) >= $date_iso
        WITH p, sum(coalesce(a.allocation_percent, 0)) AS allocation
        WITH p, (100 - allocation) AS availability
        RETURN sum(CASE WHEN availability > 0 THEN 1 ELSE 0 END) AS value
        """
        params = {"date_iso": str(date_iso).strip()}
        value = self._scalar_int(cypher, params)
        truth = GroundTruth(question_type="count", canonical=value, cypher=cypher.strip(), parameters=params)
        return EvalCase(case_id="count_available_people", question=question, ground_truth=truth)

    def _scalar_int(self, cypher: str, params: dict[str, Any]) -> int:
        rows = self._graph_service.graph.query(cypher, params) or []
        value = rows[0].get("value") if rows else 0
        return int(_parse_number(value) or 0)

    def _scalar_float(self, cypher: str, params: dict[str, Any]) -> float:
        rows = self._graph_service.graph.query(cypher, params) or []
        value = rows[0].get("value") if rows else 0.0
        return float(_parse_number(value) or 0.0)


def _parse_number(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value)
    match = re.search(r"-?\d+(?:\.\d+)?", text)
    if match is None:
        return None
    return float(match.group(0))


def _extract_first_number(text: str) -> float | None:
    return _parse_number(text)


def _score_case(truth: GroundTruth, answer_text: str) -> dict[str, Any]:
    normalized = str(answer_text or "")
    if truth.question_type == "count":
        predicted = _extract_first_number(normalized)
        expected = float(truth.canonical)
        return {
            "expected": int(expected),
            "predicted": int(predicted) if predicted is not None else None,
            "exact": bool(predicted is not None and int(predicted) == int(expected)),
        }

    if truth.question_type == "float":
        predicted = _extract_first_number(normalized)
        expected = float(truth.canonical)
        ok = False
        if predicted is not None:
            ok = abs(float(predicted) - expected) <= max(0.1, 0.05 * max(1.0, abs(expected)))
        return {
            "expected": expected,
            "predicted": float(predicted) if predicted is not None else None,
            "within_tolerance": bool(ok),
        }

    if truth.question_type == "list":
        expected_items = [str(x).strip() for x in (truth.canonical or []) if str(x).strip()]
        answer_lower = normalized.lower()
        hits = [x for x in expected_items if x.lower() in answer_lower]
        recall = (len(hits) / len(expected_items)) if expected_items else 1.0
        return {
            "expected_items": expected_items,
            "hits": hits,
            "recall": recall,
            "all_present": bool(recall >= 0.999),
        }

    return {"error": "Unsupported question type"}


def _system_answer(system: str, fn, question: str) -> SystemAnswer:
    start = datetime.now()
    try:
        payload = fn(question)
        answer = str(payload.get("answer") or "").strip()
        reasoning = str(payload.get("reasoning") or "").strip()
        elapsed_s = (datetime.now() - start).total_seconds()
        return SystemAnswer(system=system, answer=answer, reasoning=reasoning, raw=payload, elapsed_s=elapsed_s)
    except Exception as exc:
        elapsed_s = (datetime.now() - start).total_seconds()
        return SystemAnswer(
            system=system,
            answer=f"ERROR: {exc}",
            reasoning="",
            raw={"error": str(exc)},
            elapsed_s=elapsed_s,
        )


def _serialize_case_result(result: CaseResult) -> dict[str, Any]:
    return {
        "case": asdict(result.case),
        "truth": asdict(result.truth),
        "graphrag": asdict(result.graphrag),
        "vector_rag": asdict(result.vector_rag),
        "scores": result.scores,
    }


def run(*, output_dir: Path, limit: int | None = None) -> Path:
    """
    Run a deterministic evaluation comparing GraphRAG (Neo4j-backed) and Vector RAG (Chroma-backed).

    :param output_dir: directory to write result json file(s)
    :param limit: optional limit of evaluation cases
    :return: path to written json report
    """
    settings = load_settings()
    configure_logging(settings=settings)

    output_dir.mkdir(parents=True, exist_ok=True)

    graph_service = Neo4jGraphService(neo4j=settings.neo4j)
    suite = GroundTruthSuite(graph_service)
    cases = suite.build()
    if limit is not None:
        cases = cases[: max(0, int(limit))]

    results: list[CaseResult] = []
    for case in cases:
        logger.info("Evaluating case: %s", case.case_id)

        graphrag = _system_answer("graphrag", query_knowledge_graph, case.question)
        vector = _system_answer("vector_rag", query_vector_store, case.question)

        scores = {
            "graphrag": _score_case(case.ground_truth, graphrag.answer),
            "vector_rag": _score_case(case.ground_truth, vector.answer),
            "graphrag_has_reasoning": bool(graphrag.reasoning.strip()),
            "vector_rag_has_reasoning": bool(vector.reasoning.strip()),
        }

        results.append(
            CaseResult(
                case=case,
                truth=case.ground_truth,
                graphrag=graphrag,
                vector_rag=vector,
                scores=scores,
            )
        )

    summary = _summarize(results)
    payload = {
        "metadata": {
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "cases": len(results),
        },
        "summary": summary,
        "results": [_serialize_case_result(r) for r in results],
    }

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = output_dir / f"rag_comparison_{timestamp}.json"
    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    _print_summary(summary, out_path)
    return out_path


def _summarize(results: list[CaseResult]) -> dict[str, Any]:
    def case_ok(score: dict[str, Any]) -> bool:
        if "exact" in score:
            return bool(score.get("exact"))
        if "within_tolerance" in score:
            return bool(score.get("within_tolerance"))
        if "all_present" in score:
            return bool(score.get("all_present"))
        return False

    total = len(results)
    graphrag_ok = sum(1 for r in results if case_ok(r.scores.get("graphrag", {})))
    vector_ok = sum(1 for r in results if case_ok(r.scores.get("vector_rag", {})))
    graphrag_reason = sum(1 for r in results if r.scores.get("graphrag_has_reasoning"))
    vector_reason = sum(1 for r in results if r.scores.get("vector_rag_has_reasoning"))

    return {
        "total_cases": total,
        "graphrag_correct": graphrag_ok,
        "vector_rag_correct": vector_ok,
        "graphrag_accuracy": (graphrag_ok / total) if total else 0.0,
        "vector_rag_accuracy": (vector_ok / total) if total else 0.0,
        "graphrag_reasoning_rate": (graphrag_reason / total) if total else 0.0,
        "vector_rag_reasoning_rate": (vector_reason / total) if total else 0.0,
    }


def _print_summary(summary: dict[str, Any], out_path: Path) -> None:
    logger.info(
        "Report written: %s | graphrag_accuracy=%.2f | vector_accuracy=%.2f",
        out_path,
        float(summary.get("graphrag_accuracy", 0.0)),
        float(summary.get("vector_rag_accuracy", 0.0)),
    )
    print(json.dumps({"summary": summary, "report": str(out_path)}, indent=2))


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="talentmatch-rag-compare")
    parser.add_argument("--out", default="results", help="Output directory for evaluation reports")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of evaluation cases")
    return parser.parse_args()


def main() -> None:
    """
    CLI entry point for running the evaluation from terminal.
    """
    args = _parse_args()
    run(output_dir=Path(args.out), limit=args.limit)


if __name__ == "__main__":
    main()
