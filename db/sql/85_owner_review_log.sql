-- Owner answers on rule values are USER DATA: analytics.rules is rebuilt by bootstrap, so the answers live here (keyed by the rule's natural key, not its id) and are replayed after the rules load.
CREATE TABLE IF NOT EXISTS core.owner_review_log (
  id bigserial PRIMARY KEY, answered_at timestamptz NOT NULL DEFAULT now(), answer text NOT NULL CHECK (answer IN ('correct','wrong','unsure')),
  zone text, section_ref text, parameter text, status text, topic text, review_key text);
DO $$ BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='ai_readonly') THEN GRANT SELECT ON core.owner_review_log TO ai_readonly; END IF;
END $$;
