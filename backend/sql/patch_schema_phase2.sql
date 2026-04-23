-- Patch existing DBs created before Phase 2 (create_all does not ALTER tables).
-- Run: docker compose exec -T db psql -U user -d audit_nigeria -f /dev/stdin < backend/sql/patch_schema_phase2.sql
--   or copy/paste into psql.

-- uploads: quality score for consensus ranking
ALTER TABLE uploads
  ADD COLUMN IF NOT EXISTS blur_score DOUBLE PRECISION;

CREATE INDEX IF NOT EXISTS ix_uploads_blur_score ON uploads (blur_score);

-- result_clusters: consensus + JSONB party totals
ALTER TABLE result_clusters
  ADD COLUMN IF NOT EXISTS party_results JSONB;

ALTER TABLE result_clusters
  ADD COLUMN IF NOT EXISTS consensus_status VARCHAR(32) NOT NULL DEFAULT 'PENDING';

-- If current_consensus_json exists as json (not jsonb), widen to jsonb for ORM alignment.
DO $$
BEGIN
  IF EXISTS (
    SELECT 1
    FROM information_schema.columns
    WHERE table_name = 'result_clusters'
      AND column_name = 'current_consensus_json'
      AND data_type = 'json'
  ) THEN
    ALTER TABLE result_clusters
      ALTER COLUMN current_consensus_json TYPE JSONB
      USING current_consensus_json::jsonb;
  END IF;
END $$;

-- Rollup tables (safe if already created by SQLAlchemy)
CREATE TABLE IF NOT EXISTS national_result_tallies (
  election_id INTEGER PRIMARY KEY REFERENCES elections (id) ON DELETE CASCADE,
  party_results JSONB NOT NULL DEFAULT '{}'::jsonb,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS state_result_tallies (
  id SERIAL PRIMARY KEY,
  election_id INTEGER NOT NULL REFERENCES elections (id) ON DELETE CASCADE,
  state_id INTEGER NOT NULL REFERENCES states (id) ON DELETE CASCADE,
  party_results JSONB NOT NULL DEFAULT '{}'::jsonb,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT uq_state_tally_election_state UNIQUE (election_id, state_id)
);

CREATE INDEX IF NOT EXISTS ix_state_result_tallies_election_id ON state_result_tallies (election_id);
CREATE INDEX IF NOT EXISTS ix_state_result_tallies_state_id ON state_result_tallies (state_id);

CREATE TABLE IF NOT EXISTS lga_result_tallies (
  id SERIAL PRIMARY KEY,
  election_id INTEGER NOT NULL REFERENCES elections (id) ON DELETE CASCADE,
  lga_id INTEGER NOT NULL REFERENCES lgas (id) ON DELETE CASCADE,
  party_results JSONB NOT NULL DEFAULT '{}'::jsonb,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT uq_lga_tally_election_lga UNIQUE (election_id, lga_id)
);

CREATE INDEX IF NOT EXISTS ix_lga_result_tallies_election_id ON lga_result_tallies (election_id);
CREATE INDEX IF NOT EXISTS ix_lga_result_tallies_lga_id ON lga_result_tallies (lga_id);

-- polling_units: ward label from EC8A header (VLM / ingestion)
ALTER TABLE polling_units
  ADD COLUMN IF NOT EXISTS ward VARCHAR(128);
