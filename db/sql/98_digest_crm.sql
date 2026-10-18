-- Autopilot D: saved searches, digest history, CRM leads (behind the outreach flag), do-not-contact list. USER data.
CREATE TABLE IF NOT EXISTS core.user_saved_search (id bigserial PRIMARY KEY, name text NOT NULL, filters jsonb NOT NULL, created_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE IF NOT EXISTS core.user_digest (id bigserial PRIMARY KEY, generated_at timestamptz NOT NULL DEFAULT now(), since date NOT NULL, payload jsonb NOT NULL);
CREATE TABLE IF NOT EXISTS core.user_crm_lead (
  id bigserial PRIMARY KEY, parcel_id bigint, listing_id bigint, counterparty_type text CHECK (counterparty_type IN ('owner','landlord','property_manager','trustees')), contact_name text, contact_business_detail text,
  source text, lawful_basis text, contactable boolean NOT NULL DEFAULT false,
  stage text NOT NULL DEFAULT 'new' CHECK (stage IN ('new','researched','contacted','meeting','loi_offer','negotiation','conditional_signed','consent_certification','live','lost')),
  lost_reason text, assigned_rep text, priority int NOT NULL DEFAULT 3, next_action text, next_action_on date, notes text, created_at timestamptz NOT NULL DEFAULT now(),
  CHECK (NOT contactable OR (source IS NOT NULL AND lawful_basis IS NOT NULL AND counterparty_type IS NOT NULL)));
CREATE TABLE IF NOT EXISTS core.user_crm_activity (id bigserial PRIMARY KEY, lead_id bigint NOT NULL REFERENCES core.user_crm_lead(id), kind text NOT NULL CHECK (kind IN ('visit','call','email','letter','meeting','note')), outcome text, notes text, at timestamptz NOT NULL DEFAULT now());
CREATE TABLE IF NOT EXISTS core.user_crm_do_not_contact (id bigserial PRIMARY KEY, contact_name text, business_detail text, parcel_id bigint, reason text NOT NULL, added_on date NOT NULL DEFAULT current_date);
DO $$ BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='app_rw') THEN
    GRANT SELECT, INSERT, UPDATE, DELETE ON core.user_saved_search, core.user_digest, core.user_crm_lead, core.user_crm_activity, core.user_crm_do_not_contact TO app_rw; GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA core TO app_rw; END IF;
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='ai_readonly') THEN GRANT SELECT ON core.user_saved_search, core.user_digest TO ai_readonly; END IF;
END $$;
