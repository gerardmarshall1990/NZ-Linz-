-- Autopilot G (Part 8 scale design): tasks, engineers and batch review workflow, capture portal links, touchpoint roles, stage probabilities. USER data.
ALTER TABLE core.rh_effort_log ADD COLUMN IF NOT EXISTS role text;
CREATE TABLE IF NOT EXISTS core.user_task (id bigserial PRIMARY KEY, title text NOT NULL, assignee text, due_on date, status text NOT NULL DEFAULT 'open' CHECK (status IN ('open','done','cancelled')), subject_type text, subject_id bigint, created_at timestamptz NOT NULL DEFAULT now(), done_at timestamptz);
CREATE TABLE IF NOT EXISTS core.user_engineer (id bigserial PRIMARY KEY, name text NOT NULL, company text, discipline text NOT NULL CHECK (discipline IN ('designer','fire','structural','services','other')), fee_per_review numeric, target_turnaround_days int, review_window text, active boolean NOT NULL DEFAULT true);
CREATE TABLE IF NOT EXISTS core.user_comment_template (id bigserial PRIMARY KEY, title text NOT NULL, body text NOT NULL, discipline text);
ALTER TABLE core.rh_review_package ADD COLUMN IF NOT EXISTS engineer_id bigint REFERENCES core.user_engineer(id), ADD COLUMN IF NOT EXISTS due_on date, ADD COLUMN IF NOT EXISTS escalated_at timestamptz, ADD COLUMN IF NOT EXISTS fee numeric;
CREATE TABLE IF NOT EXISTS core.user_capture_link (id bigserial PRIMARY KEY, parcel_id bigint NOT NULL, token_hash text NOT NULL UNIQUE, expires_at timestamptz NOT NULL, retention_until date NOT NULL, status text NOT NULL DEFAULT 'open' CHECK (status IN ('open','complete','cancelled')),
  permission_by text, permission_role text, permission_at timestamptz, submission jsonb NOT NULL DEFAULT '{}'::jsonb, last_activity timestamptz, created_at timestamptz NOT NULL DEFAULT now());
DO $$ BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='app_rw') THEN
    GRANT SELECT, INSERT, UPDATE, DELETE ON core.user_task, core.user_engineer, core.user_comment_template, core.user_capture_link TO app_rw; GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA core TO app_rw; END IF;
END $$;
ALTER TABLE core.rh_review_event DROP CONSTRAINT IF EXISTS rh_review_event_kind_check;
ALTER TABLE core.rh_review_event ADD CONSTRAINT rh_review_event_kind_check CHECK (kind IN ('created','sent','viewed','comment','returned','cancelled','assigned','escalated'));
