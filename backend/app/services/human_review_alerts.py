"""Human-in-the-loop: Telegram when multi-upload consensus confidence is low."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models import ResultCluster
from app.services.telegram_notify import send_telegram_text

logger = logging.getLogger(__name__)


def _review_urls(*, pu_id: int, election_id: int, cluster_id: int) -> tuple[str, str]:
    base = (settings.FRONTEND_PUBLIC_BASE_URL or "").rstrip("/")
    api = settings.PUBLIC_BASE_URL.rstrip("/")
    dash = f"{base}/evidence/0?pu_id={pu_id}&election_id={election_id}" if base else ""
    api_line = f"{api}/results/clusters/{cluster_id}/consensus"
    return dash, api_line


async def maybe_telegram_low_confidence_after_multi_upload(
    session: AsyncSession,
    *,
    cluster_id: int,
    election_id: int,
    pu_id: int,
    upload_count: int,
) -> None:
    """
    After ≥2 uploads for a cluster, if match strength is below threshold and we have not
    alerted yet, send Telegram with dashboard + API hints.
    """
    token = (settings.TELEGRAM_BOT_TOKEN or "").strip()
    if not token or not (settings.TELEGRAM_CHAT_IDS or "").strip():
        return
    if upload_count < 2:
        return

    cluster = await session.get(ResultCluster, cluster_id)
    if cluster is None or cluster.human_review_alert_sent_at is not None:
        return

    conf_f = cluster.confidence_score
    if isinstance(conf_f, (int, float)):
        conf_f = float(conf_f)
    else:
        conf_f = None

    thr = float(settings.TELEGRAM_HIL_CONFIDENCE_BELOW)
    low = conf_f is None or conf_f < thr
    if not low:
        return

    status = str(cluster.consensus_status or "")
    reason = ""
    cons = cluster.current_consensus_json
    if isinstance(cons, dict):
        r = cons.get("reason")
        if r is not None:
            reason = str(r)

    dash, api_put = _review_urls(pu_id=pu_id, election_id=election_id, cluster_id=cluster_id)
    lines = [
        "Audit Nigeria — sheet needs human review",
        f"PU id: {pu_id} | Election id: {election_id} | Cluster id: {cluster_id}",
        f"Status: {status} | Match strength: {(conf_f if conf_f is not None else 'n/a')}",
    ]
    if reason:
        lines.append(f"Reason: {reason}")
    if dash:
        lines.append(f"Dashboard: {dash}")
    lines.append(f"Admin API (PUT JSON): {api_put}")
    lines.append("Use your admin token / OpenAPI to send corrected party_results + summary.")

    await send_telegram_text("\n".join(lines))
    cluster.human_review_alert_sent_at = datetime.now(tz=UTC)
    await session.flush()
    logger.info(
        "human_review_alerts: telegram sent cluster_id=%s pu_id=%s conf=%s uploads=%s",
        cluster_id,
        pu_id,
        conf_f,
        upload_count,
    )
