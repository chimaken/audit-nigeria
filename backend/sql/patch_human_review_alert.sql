-- One-shot flag: Telegram human-in-the-loop alert already sent for this cluster (until cleared on manual review).
ALTER TABLE result_clusters
  ADD COLUMN IF NOT EXISTS human_review_alert_sent_at TIMESTAMPTZ;
