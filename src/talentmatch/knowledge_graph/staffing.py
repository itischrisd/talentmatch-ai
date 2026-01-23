from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import date, timedelta
from functools import lru_cache
from typing import Any, Iterable

from talentmatch.config import load_settings
from talentmatch.knowledge_graph.neo4j import Neo4jGraphService

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class SkillRequirement:
    skill_id: str
    min_level: str | None
    is_mandatory: bool


@dataclass(frozen=True, slots=True)
class RfpProfile:
    rfp_id: str
    title: str | None
    start_date: date | None
    end_date: date | None
    duration_months: int | None
    team_size: int | None
    requirements: tuple[SkillRequirement, ...]


@dataclass(frozen=True, slots=True)
class CandidateProfile:
    person_id: str
    name: str | None
    skills: dict[str, str]
    availability_percent: int


def propose_staffing(request: str) -> dict[str, Any]:
    """
    Propose a best-effort staffing for an RFP based on the current Neo4j knowledge graph.

    The result is always non-empty: if no internal candidates can be selected, an external placeholder offer is returned.

    :param request: user request containing an RFP id (e.g. "RFP-001") or a short staffing request
    :return: dict with staffing proposal, coverage summary and explainable reasoning
    """
    normalized = request.strip()
    if not normalized:
        return _empty_request_payload()

    engine = _get_engine()
    rfp_id = engine.extract_rfp_id(normalized)

    rfp = engine.load_rfp(rfp_id) if rfp_id else None
    requirements = rfp.requirements if rfp else tuple()

    team_size = (rfp.team_size if rfp and rfp.team_size and rfp.team_size > 0 else None) or _default_team_size(
        requirements=requirements
    )

    candidates = engine.load_candidates(rfp=rfp)
    if not candidates:
        return _external_only_payload(request=normalized, rfp=rfp, team_size=team_size)

    selection = engine.select_team(
        candidates=candidates,
        requirements=requirements,
        team_size=team_size,
    )

    if not selection:
        return _external_only_payload(request=normalized, rfp=rfp, team_size=team_size)

    payload = engine.build_payload(
        request=normalized,
        rfp=rfp,
        requirements=requirements,
        selection=selection,
        team_size=team_size,
    )
    return payload


def _empty_request_payload() -> dict[str, Any]:
    return {
        "request": "",
        "rfp": None,
        "team": [
            {
                "person_id": "EXTERNAL",
                "name": "External contractor",
                "availability_percent": 100,
                "matched_requirements": [],
                "gaps": [],
                "reasoning": "Empty request; returning a placeholder external staffing offer.",
            }
        ],
        "coverage": {"covered_skills": [], "missing_skills": [], "mandatory_missing_skills": []},
        "reasoning": "A staffing offer must be produced even for an empty request; returning a placeholder.",
        "limitations": "Provide an RFP id like RFP-001 to get an internal staffing proposal.",
    }


def _external_only_payload(request: str, rfp: RfpProfile | None, team_size: int) -> dict[str, Any]:
    slots = max(int(team_size), 1)
    team = [
        {
            "person_id": "EXTERNAL",
            "name": "External contractor",
            "availability_percent": 100,
            "matched_requirements": [],
            "gaps": [req.skill_id for req in (rfp.requirements if rfp else tuple())],
            "reasoning": "No internal candidates were found or selected; offering an external staffing placeholder.",
        }
        for _ in range(slots)
    ]
    requirements = rfp.requirements if rfp else tuple()
    missing = [r.skill_id for r in requirements]
    mandatory_missing = [r.skill_id for r in requirements if r.is_mandatory]
    return {
        "request": request,
        "rfp": _rfp_to_dict(rfp),
        "team": team,
        "coverage": {"covered_skills": [], "missing_skills": missing, "mandatory_missing_skills": mandatory_missing},
        "reasoning": "No internal staffing could be constructed; returning an external offer to satisfy the requirement.",
        "limitations": "Ingest CV/RFP PDFs (and project assignments) into Neo4j to enable internal staffing proposals.",
    }


def _rfp_to_dict(rfp: RfpProfile | None) -> dict[str, Any] | None:
    if rfp is None:
        return None
    return {
        "id": rfp.rfp_id,
        "title": rfp.title,
        "start_date": rfp.start_date.isoformat() if rfp.start_date else None,
        "end_date": rfp.end_date.isoformat() if rfp.end_date else None,
        "duration_months": rfp.duration_months,
        "team_size": rfp.team_size,
        "requirements": [
            {"skill_id": r.skill_id, "min_level": r.min_level, "is_mandatory": r.is_mandatory} for r in rfp.requirements
        ],
    }


def _default_team_size(*, requirements: tuple[SkillRequirement, ...]) -> int:
    return max(len(requirements), 1)


@dataclass(frozen=True, slots=True)
class _Engine:
    graph_service: Neo4jGraphService
    proficiency_levels: tuple[str, ...]

    @staticmethod
    def extract_rfp_id(request: str) -> str | None:
        match = re.search(r"\bRFP-\d{3}\b", request.upper())
        return match.group(0) if match else None

    def load_rfp(self, rfp_id: str) -> RfpProfile | None:
        rows = self.graph_service.graph.query(
            """
            MATCH (r:RFP {id: $rfp_id})
            OPTIONAL MATCH (r)-[rel:REQUIRES]->(s:Skill)
            RETURN
              r.id AS id,
              r.title AS title,
              r.start_date AS start_date,
              r.duration_months AS duration_months,
              r.team_size AS team_size,
              collect({
                skill_id: s.id,
                level: coalesce(rel.level, rel.min_proficiency, s.level),
                mandatory: coalesce(rel.is_mandatory, rel.mandatory, true)
              }) AS requirements
            """,
            {"rfp_id": rfp_id},
        )
        if not rows:
            return None

        row = rows[0]
        start = _parse_date(row.get("start_date"))
        duration = _parse_int(row.get("duration_months"))
        end = _compute_end_date(start=start, duration_months=duration)

        raw_reqs = row.get("requirements") or []
        requirements = tuple(_to_requirement(item) for item in raw_reqs if _to_requirement(item) is not None)

        return RfpProfile(
            rfp_id=str(row.get("id") or rfp_id),
            title=_none_if_blank(row.get("title")),
            start_date=start,
            end_date=end,
            duration_months=duration,
            team_size=_parse_int(row.get("team_size")),
            requirements=requirements,
        )

    def load_candidates(self, *, rfp: RfpProfile | None) -> list[CandidateProfile]:
        people = self._load_people_skills()
        if not people:
            return []

        start_str, end_str = _rfp_window_strings(rfp)
        availability = self._load_availability(
            person_ids=[p["person_id"] for p in people],
            start_date=start_str,
            end_date=end_str,
        )
        profiles: list[CandidateProfile] = []
        for item in people:
            person_id = str(item.get("person_id") or "").strip()
            if not person_id:
                continue
            profiles.append(
                CandidateProfile(
                    person_id=person_id,
                    name=_none_if_blank(item.get("name")),
                    skills=_skills_dict(item.get("skills") or []),
                    availability_percent=int(availability.get(person_id, 100)),
                )
            )
        return profiles

    def select_team(
            self,
            *,
            candidates: list[CandidateProfile],
            requirements: tuple[SkillRequirement, ...],
            team_size: int,
    ) -> list[CandidateProfile]:
        if team_size <= 0:
            return []

        remaining = {c.person_id: c for c in candidates}
        selected: list[CandidateProfile] = []
        uncovered = {r.skill_id for r in requirements if r.skill_id}

        while remaining and len(selected) < team_size:
            best = self._pick_next(
                remaining=list(remaining.values()),
                requirements=requirements,
                uncovered=uncovered,
            )
            if best is None:
                break
            selected.append(best)
            remaining.pop(best.person_id, None)
            uncovered -= self._covered_skills(best, requirements=requirements)

        if len(selected) < team_size and remaining:
            fillers = sorted(
                remaining.values(),
                key=lambda c: self._overall_rank_key(c, requirements=requirements),
            )
            for c in fillers:
                if len(selected) >= team_size:
                    break
                selected.append(c)

        return selected[:team_size]

    def build_payload(
            self,
            *,
            request: str,
            rfp: RfpProfile | None,
            requirements: tuple[SkillRequirement, ...],
            selection: list[CandidateProfile],
            team_size: int,
    ) -> dict[str, Any]:
        covered = _covered_by_team(selection, requirements=requirements)
        missing = [r.skill_id for r in requirements if r.skill_id and r.skill_id not in covered]
        mandatory_missing = [r.skill_id for r in requirements if r.is_mandatory and r.skill_id not in covered]

        team = [
            self._candidate_to_payload(
                c,
                requirements=requirements,
                covered_skills=self._covered_skills(c, requirements=requirements),
            )
            for c in selection
        ]

        reasoning = self._overall_reasoning(
            rfp=rfp,
            requirements=requirements,
            team=selection,
            covered=covered,
            missing=missing,
            mandatory_missing=mandatory_missing,
            team_size=team_size,
        )

        return {
            "request": request,
            "rfp": _rfp_to_dict(rfp),
            "team": team,
            "coverage": {
                "covered_skills": sorted(covered),
                "missing_skills": missing,
                "mandatory_missing_skills": mandatory_missing,
            },
            "reasoning": reasoning,
            "limitations": _limitations_text(rfp=rfp, requirements=requirements),
        }

    def _candidate_to_payload(
            self,
            candidate: CandidateProfile,
            *,
            requirements: tuple[SkillRequirement, ...],
            covered_skills: set[str],
    ) -> dict[str, Any]:
        matches = []
        gaps = []
        for req in requirements:
            skill_id = req.skill_id
            if not skill_id:
                continue
            have_level = candidate.skills.get(skill_id)
            if have_level is None:
                gaps.append(skill_id)
                continue
            if self._meets_requirement(have_level, req.min_level):
                matches.append(
                    {
                        "skill_id": skill_id,
                        "required_level": req.min_level,
                        "candidate_level": have_level,
                        "match": "meets_or_exceeds",
                        "overqualification_steps": self._overqualification_steps(have_level, req.min_level),
                    }
                )
            else:
                gaps.append(skill_id)

        reasoning = self._candidate_reasoning(
            candidate=candidate,
            requirements=requirements,
            covered_skills=covered_skills,
            gaps=gaps,
        )

        return {
            "person_id": candidate.person_id,
            "name": candidate.name,
            "availability_percent": candidate.availability_percent,
            "matched_requirements": matches,
            "gaps": gaps,
            "reasoning": reasoning,
        }

    def _pick_next(
            self,
            *,
            remaining: list[CandidateProfile],
            requirements: tuple[SkillRequirement, ...],
            uncovered: set[str],
    ) -> CandidateProfile | None:
        if not remaining:
            return None

        ranked = sorted(
            remaining,
            key=lambda c: self._marginal_rank_key(c, requirements=requirements, uncovered=uncovered),
        )
        best = ranked[0] if ranked else None
        if best is None:
            return None

        best_gain = self._marginal_gain(best, requirements=requirements, uncovered=uncovered)
        if best_gain <= 0:
            ranked = sorted(remaining, key=lambda c: self._overall_rank_key(c, requirements=requirements))
            return ranked[0] if ranked else None

        return best

    def _marginal_gain(
            self,
            candidate: CandidateProfile,
            *,
            requirements: tuple[SkillRequirement, ...],
            uncovered: set[str],
    ) -> int:
        gain = 0
        for req in requirements:
            if req.skill_id in uncovered and self._candidate_covers(candidate, req):
                gain += 1
        return gain

    def _covered_skills(self, candidate: CandidateProfile, *, requirements: tuple[SkillRequirement, ...]) -> set[str]:
        return {req.skill_id for req in requirements if req.skill_id and self._candidate_covers(candidate, req)}

    def _candidate_covers(self, candidate: CandidateProfile, req: SkillRequirement) -> bool:
        have = candidate.skills.get(req.skill_id)
        if have is None:
            return False
        return self._meets_requirement(have, req.min_level)

    def _meets_requirement(self, have_level: str, min_level: str | None) -> bool:
        if min_level is None:
            return True
        return self._level_rank(have_level) >= self._level_rank(min_level)

    def _overqualification_steps(self, have_level: str, min_level: str | None) -> int | None:
        if min_level is None:
            return None
        have = self._level_rank(have_level)
        need = self._level_rank(min_level)
        return max(have - need, 0)

    def _level_rank(self, level: str) -> int:
        normalized = str(level or "").strip().lower()
        if not normalized:
            return len(self.proficiency_levels)
        for idx, item in enumerate(self.proficiency_levels):
            if normalized == item.strip().lower():
                return idx
        return len(self.proficiency_levels)

    def _marginal_rank_key(
            self,
            candidate: CandidateProfile,
            *,
            requirements: tuple[SkillRequirement, ...],
            uncovered: set[str],
    ) -> tuple[int, int, int, int, str]:
        gain = 0
        overqual = 0
        for req in requirements:
            if req.skill_id not in uncovered:
                continue
            have = candidate.skills.get(req.skill_id)
            if have is None:
                continue
            if self._meets_requirement(have, req.min_level):
                gain += 1
                overqual += int(self._overqualification_steps(have, req.min_level) or 0)
        overall_overqual = self._total_overqualification(candidate, requirements=requirements)
        return -gain, overqual, -candidate.availability_percent, overall_overqual, candidate.person_id

    def _overall_rank_key(
            self,
            candidate: CandidateProfile,
            *,
            requirements: tuple[SkillRequirement, ...],
    ) -> tuple[int, int, int, str]:
        coverage = sum(1 for req in requirements if self._candidate_covers(candidate, req))
        overqual = self._total_overqualification(candidate, requirements=requirements)
        return -coverage, overqual, -candidate.availability_percent, candidate.person_id

    def _total_overqualification(self, candidate: CandidateProfile, *,
                                 requirements: tuple[SkillRequirement, ...]) -> int:
        total = 0
        for req in requirements:
            have = candidate.skills.get(req.skill_id)
            if have is None:
                continue
            if not self._meets_requirement(have, req.min_level):
                continue
            total += int(self._overqualification_steps(have, req.min_level) or 0)
        return total

    def _candidate_reasoning(
            self,
            *,
            candidate: CandidateProfile,
            requirements: tuple[SkillRequirement, ...],
            covered_skills: set[str],
            gaps: list[str],
    ) -> str:
        req_count = len([r for r in requirements if r.skill_id])
        coverage = len(covered_skills)
        if req_count <= 0:
            return f"Selected as an available candidate (availability {candidate.availability_percent}%)."

        overqual = self._total_overqualification(candidate, requirements=requirements)
        parts = [
            f"Covers {coverage}/{req_count} required skills.",
            f"Availability {candidate.availability_percent}%.",
        ]
        if overqual > 0:
            parts.append(f"Overqualification steps sum: {overqual}.")
        if gaps:
            parts.append(f"Missing: {', '.join(sorted(set(gaps)))}.")
        return " ".join(parts)

    @staticmethod
    def _overall_reasoning(
            *,
            rfp: RfpProfile | None,
            requirements: tuple[SkillRequirement, ...],
            team: list[CandidateProfile],
            covered: set[str],
            missing: list[str],
            mandatory_missing: list[str],
            team_size: int,
    ) -> str:
        base = []
        if rfp is None:
            base.append("RFP not found; proposal is based on the request text and global candidate pool.")
        else:
            base.append(f"RFP {rfp.rfp_id} staffing proposal assembled from Neo4j knowledge graph.")
            if rfp.start_date and rfp.end_date:
                base.append(f"Availability window: {rfp.start_date.isoformat()} to {rfp.end_date.isoformat()}.")

        req_skills = [r.skill_id for r in requirements if r.skill_id]
        if req_skills:
            base.append(f"Requirements: {', '.join(sorted(set(req_skills)))}.")
            base.append(f"Covered skills: {', '.join(sorted(covered))}." if covered else "Covered skills: none.")
            if missing:
                base.append(f"Missing skills: {', '.join(sorted(set(missing)))}.")
            if mandatory_missing:
                base.append(f"Mandatory gaps: {', '.join(sorted(set(mandatory_missing)))}.")
        else:
            base.append(
                "No explicit requirements were found in the graph; selecting the most reasonable team by availability and general fit.")

        if team:
            base.append(f"Team size: {len(team)}/{max(team_size, 1)}.")
        return " ".join(base)

    def _load_people_skills(self) -> list[dict[str, Any]]:
        rows = self.graph_service.graph.query(
            """
            MATCH (p:Person)
            OPTIONAL MATCH (p)-[hs:HAS_SKILL]->(s:Skill)
            RETURN
              p.id AS person_id,
              coalesce(p.name, p.full_name, p.id) AS name,
              collect({skill_id: s.id, level: coalesce(hs.level, s.level)}) AS skills
            """
        )
        return list(rows or [])

    def _load_availability(self, *, person_ids: list[str], start_date: str | None, end_date: str | None) -> dict[
        str, int]:
        if not person_ids or not start_date or not end_date:
            return {pid: 100 for pid in person_ids}

        rows = self.graph_service.graph.query(
            """
            UNWIND $person_ids AS pid
            MATCH (p:Person {id: pid})
            OPTIONAL MATCH (p)-[a:ASSIGNED_TO]->(:Project)
            WHERE
              coalesce(a.start_date, a.assignment_start_date) <= $end_date
              AND coalesce(a.end_date, a.assignment_end_date) >= $start_date
            RETURN
              pid AS person_id,
              sum(coalesce(a.allocation_percent, 0)) AS allocation
            """,
            {"person_ids": person_ids, "start_date": start_date, "end_date": end_date},
        )

        availability: dict[str, int] = {pid: 100 for pid in person_ids}
        for row in rows or []:
            pid = str(row.get("person_id") or "").strip()
            if not pid:
                continue
            allocation = _parse_int(row.get("allocation")) or 0
            availability[pid] = max(0, min(100, 100 - allocation))
        return availability


@lru_cache(maxsize=1)
def _get_engine() -> _Engine:
    settings = load_settings()
    graph_service = Neo4jGraphService(neo4j=settings.neo4j)
    proficiency_levels = tuple(str(x) for x in (settings.datasets.skills.proficiency_levels or []))
    return _Engine(graph_service=graph_service, proficiency_levels=proficiency_levels)


def _skills_dict(items: Iterable[dict[str, Any]]) -> dict[str, str]:
    result: dict[str, str] = {}
    for raw in items:
        skill_id = _none_if_blank(raw.get("skill_id"))
        if not skill_id:
            continue
        level = _none_if_blank(raw.get("level")) or ""
        if level:
            result[skill_id] = level
    return result


def _to_requirement(raw: Any) -> SkillRequirement | None:
    if not isinstance(raw, dict):
        return None
    skill_id = _none_if_blank(raw.get("skill_id"))
    if not skill_id:
        return None
    min_level = _none_if_blank(raw.get("level"))
    mandatory = raw.get("mandatory")
    is_mandatory = True if mandatory is None else bool(mandatory)
    return SkillRequirement(skill_id=skill_id, min_level=min_level, is_mandatory=is_mandatory)


def _none_if_blank(value: Any) -> str | None:
    text = str(value).strip() if value is not None else ""
    return text if text else None


def _parse_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _parse_date(value: Any) -> date | None:
    raw = _none_if_blank(value)
    if not raw:
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return None


def _compute_end_date(*, start: date | None, duration_months: int | None) -> date | None:
    if start is None or duration_months is None:
        return None
    return start + timedelta(days=int(duration_months) * 30)


def _covered_by_team(team: list[CandidateProfile], *, requirements: tuple[SkillRequirement, ...]) -> set[str]:
    required = [r for r in requirements if r.skill_id]
    covered: set[str] = set()
    for req in required:
        for candidate in team:
            have = candidate.skills.get(req.skill_id)
            if have is not None:
                covered.add(req.skill_id)
                break
    return covered


def _rfp_window_strings(rfp: RfpProfile | None) -> tuple[str | None, str | None]:
    if rfp is None or rfp.start_date is None or rfp.end_date is None:
        return None, None
    return rfp.start_date.isoformat(), rfp.end_date.isoformat()


def _limitations_text(*, rfp: RfpProfile | None, requirements: tuple[SkillRequirement, ...]) -> str | None:
    notes = []
    if rfp is None:
        notes.append("RFP id was not found in the graph; provide a valid id like RFP-001.")
    if requirements and any(r.min_level is None for r in requirements):
        notes.append("Some requirement proficiency levels were missing; those were treated as satisfied by any level.")
    if requirements and any(r.is_mandatory for r in requirements) and not any(
            key in ("mandatory", "is_mandatory") for key in ("mandatory", "is_mandatory")
    ):
        notes.append(
            "Mandatory vs preferred flags may not be preserved by the KG transformer; treated as mandatory by default.")
    return " ".join(notes) if notes else None
