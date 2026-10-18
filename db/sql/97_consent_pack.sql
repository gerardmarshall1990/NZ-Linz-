-- Part 7 step 4: building consent pack, statements and register checks, engineer review packages. USER/derived data: named core.rh_* so it is in the user-data backup.
CREATE TABLE IF NOT EXISTS core.rh_pack (
  id bigserial PRIMARY KEY, parcel_id bigint NOT NULL REFERENCES core.rh_property(parcel_id), option_id bigint REFERENCES core.rh_layout_option(id), version int NOT NULL,
  status text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','ready_to_lodge','superseded')), checklist_version text NOT NULL, inputs jsonb NOT NULL, superseded_by bigint,
  created_at timestamptz NOT NULL DEFAULT now(), ready_marked_at timestamptz);
CREATE TABLE IF NOT EXISTS core.rh_pack_doc (
  id bigserial PRIMARY KEY, pack_id bigint NOT NULL REFERENCES core.rh_pack(id) ON DELETE CASCADE, doc_key text NOT NULL, title text NOT NULL, kind text NOT NULL CHECK (kind IN ('generated','upload_slot','form_data')),
  folder text, file_name text, required boolean NOT NULL DEFAULT true, not_required_reason text, owner text, source text, statement_type text, discipline text, content_md text, UNIQUE (pack_id, doc_key));
CREATE TABLE IF NOT EXISTS core.rh_statement (
  id bigserial PRIMARY KEY, doc_id bigint NOT NULL REFERENCES core.rh_pack_doc(id) ON DELETE CASCADE, original_name text NOT NULL, stored_name text NOT NULL, sha256 text NOT NULL, size_bytes bigint NOT NULL,
  statement_type text NOT NULL, author_name text, author_company text, psa_number text, discipline text, date_issued date, scope_note text,
  register_status text NOT NULL DEFAULT 'not_checked' CHECK (register_status IN ('not_checked','valid','not_on_register','expired','not_applicable')), register_checked_on date, register_checked_by text, register_note text,
  uploaded_at timestamptz NOT NULL DEFAULT now(), superseded boolean NOT NULL DEFAULT false);
CREATE TABLE IF NOT EXISTS core.rh_review_package (
  id bigserial PRIMARY KEY, pack_id bigint NOT NULL REFERENCES core.rh_pack(id) ON DELETE CASCADE, role text NOT NULL CHECK (role IN ('designer','fire','structural','services')), engineer_name text, engineer_company text,
  token_hash text, expires_at timestamptz, status text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','sent','commented','returned','cancelled')), version int NOT NULL DEFAULT 1,
  created_at timestamptz NOT NULL DEFAULT now(), sent_at timestamptz, returned_at timestamptz);
CREATE TABLE IF NOT EXISTS core.rh_review_event (
  id bigserial PRIMARY KEY, package_id bigint NOT NULL REFERENCES core.rh_review_package(id) ON DELETE CASCADE, kind text NOT NULL CHECK (kind IN ('created','sent','viewed','comment','returned','cancelled')), author text, body text, at timestamptz NOT NULL DEFAULT now());
CREATE TABLE IF NOT EXISTS core.user_flag (key text PRIMARY KEY, enabled boolean NOT NULL DEFAULT false, changed_at timestamptz NOT NULL DEFAULT now(), changed_by text, note text);
DO $$ BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='app_rw') THEN
    GRANT SELECT, INSERT, UPDATE, DELETE ON core.rh_pack, core.rh_pack_doc, core.rh_statement, core.rh_review_package, core.rh_review_event, core.user_flag TO app_rw; GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA core TO app_rw; END IF;
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='ai_readonly') THEN GRANT SELECT ON core.rh_pack, core.rh_pack_doc, core.user_flag TO ai_readonly; END IF;
END $$;
