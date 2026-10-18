-- Autopilot B/C: approval records, lodgement record, RFI tracker, milestones, effort log, parallel tracks, certification checklist. USER data (core.rh_*).
CREATE TABLE IF NOT EXISTS core.rh_approval (
  id bigserial PRIMARY KEY, kind text NOT NULL, subject_type text NOT NULL, subject_id bigint NOT NULL, summary text NOT NULL, draft_text text,
  status text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','granted','rejected')), requested_at timestamptz NOT NULL DEFAULT now(),
  decided_at timestamptz, decided_by text, note text, used_at timestamptz);
ALTER TABLE core.rh_approval DROP CONSTRAINT IF EXISTS rh_approval_status_check;
UPDATE core.rh_approval SET status='granted' WHERE status='approved';
ALTER TABLE core.rh_approval ADD CONSTRAINT rh_approval_status_check CHECK (status IN ('pending','granted','rejected'));
CREATE INDEX IF NOT EXISTS rh_approval_subject ON core.rh_approval (kind, subject_type, subject_id);
CREATE TABLE IF NOT EXISTS core.rh_lodgement (id bigserial PRIMARY KEY, pack_id bigint NOT NULL REFERENCES core.rh_pack(id), approval_id bigint NOT NULL REFERENCES core.rh_approval(id),
  portal_ref text NOT NULL, lodged_on date NOT NULL, note text, created_at timestamptz NOT NULL DEFAULT now());
ALTER TABLE core.rh_pack DROP CONSTRAINT IF EXISTS rh_pack_status_check;
ALTER TABLE core.rh_pack ADD CONSTRAINT rh_pack_status_check CHECK (status IN ('draft','ready_to_lodge','lodged','superseded'));
CREATE TABLE IF NOT EXISTS core.rh_rfi (
  id bigserial PRIMARY KEY, parcel_id bigint NOT NULL REFERENCES core.rh_property(parcel_id), pack_id bigint REFERENCES core.rh_pack(id), council_ref text, received_on date NOT NULL, due_on date,
  summary text NOT NULL, status text NOT NULL DEFAULT 'open' CHECK (status IN ('open','responded','closed')), responded_on date, created_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE IF NOT EXISTS core.rh_rfi_item (
  id bigserial PRIMARY KEY, rfi_id bigint NOT NULL REFERENCES core.rh_rfi(id) ON DELETE CASCADE, text text NOT NULL, owner_role text, status text NOT NULL DEFAULT 'open' CHECK (status IN ('open','answered','not_applicable')), response text);
CREATE TABLE IF NOT EXISTS core.rh_milestone (
  parcel_id bigint NOT NULL REFERENCES core.rh_property(parcel_id), key text NOT NULL, planned_on date, actual_on date, note text, PRIMARY KEY (parcel_id, key));
CREATE TABLE IF NOT EXISTS core.rh_effort_log (
  id bigserial PRIMARY KEY, parcel_id bigint, step text NOT NULL, minutes numeric NOT NULL CHECK (minutes >= 0), note text, at timestamptz NOT NULL DEFAULT now());
CREATE TABLE IF NOT EXISTS core.rh_cert_item (
  parcel_id bigint NOT NULL REFERENCES core.rh_property(parcel_id), key text NOT NULL, status text NOT NULL DEFAULT 'not_started' CHECK (status IN ('not_started','in_progress','done','not_applicable')), note text, updated_at timestamptz NOT NULL DEFAULT now(), PRIMARY KEY (parcel_id, key));
DO $$ BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='app_rw') THEN
    GRANT SELECT, INSERT, UPDATE, DELETE ON core.rh_approval, core.rh_lodgement, core.rh_rfi, core.rh_rfi_item, core.rh_milestone, core.rh_effort_log, core.rh_cert_item TO app_rw; GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA core TO app_rw; END IF;
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='ai_readonly') THEN GRANT SELECT ON core.rh_approval, core.rh_lodgement, core.rh_rfi, core.rh_rfi_item, core.rh_milestone, core.rh_effort_log, core.rh_cert_item TO ai_readonly; END IF;
END $$;
