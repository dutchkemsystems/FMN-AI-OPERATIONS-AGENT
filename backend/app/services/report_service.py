"""Report service — executive report builder."""
from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from ..models.database import ActionLog, AgentRun, Report, utcnow


def build_executive_report(
    db: Session,
    settings: Any,
    agent_summaries: list[dict],
) -> Report:
    """Aggregate agent run results into an executive report."""
    total_actions = 0
    errors = 0
    agent_results: dict[str, dict] = {}
    for summary in agent_summaries:
        name = summary.get("agent", "unknown")
        agent_results[name] = {
            "status": summary.get("status", "unknown"),
            "actions_count": len(summary.get("actions", [])),
        }
        total_actions += len(summary.get("actions", []))
        if summary.get("error"):
            errors += 1

    recent_logs = (
        db.query(ActionLog)
        .order_by(ActionLog.timestamp.desc())
        .limit(50)
        .all()
    )
    recent_runs = (
        db.query(AgentRun)
        .order_by(AgentRun.timestamp.desc())
        .limit(20)
        .all()
    )

    impact_total = sum(
        log.impact_ngn for log in recent_logs if log.impact_ngn
    )

    content = {
        "summary": {
            "agents_run": len(agent_summaries),
            "total_actions": total_actions,
            "errors": errors,
            "impact_ngn": round(impact_total, 0),
        },
        "agents": agent_results,
        "recent_runs": [
            {
                "agent": r.agent_type,
                "status": r.status,
                "duration_ms": r.duration_ms,
                "actions": r.num_actions,
            }
            for r in recent_runs
        ],
        "top_actions": [
            {
                "agent": log.agent_type,
                "action": log.action_type,
                "status": log.status,
                "impact": log.impact_ngn,
            }
            for log in recent_logs[:10]
        ],
    }

    report = Report(
        title=f"Executive Report — {utcnow().strftime('%Y-%m-%d %H:%M')}",
        kind="executive",
        content=content,
    )
    db.add(report)
    db.flush()
    return report
