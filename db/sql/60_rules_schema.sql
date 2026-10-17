-- Rules corpus schema (SPEC 2, section 2). Re-runnable: drops and recreates the rules tables.
SET client_min_messages = warning;
CREATE EXTENSION IF NOT EXISTS vector;
DROP TABLE IF EXISTS analytics.rule_text_chunks CASCADE; DROP TABLE IF EXISTS analytics.rules CASCADE; DROP TABLE IF EXISTS analytics.source_documents CASCADE;

CREATE TABLE analytics.source_documents (
  id serial PRIMARY KEY, council text NOT NULL, doc_kind text NOT NULL, chapter text, title text NOT NULL, url text NOT NULL,
  sha256 text, bytes bigint, plan_version_id int REFERENCES analytics.plan_versions(id), index_date text, retrieved_at date NOT NULL);

CREATE TABLE analytics.rule_text_chunks (
  id serial PRIMARY KEY, source_document_id int REFERENCES analytics.source_documents(id), council text NOT NULL, chapter text NOT NULL,
  section_ref text NOT NULL, ref_unverified boolean NOT NULL DEFAULT false, heading text, page_start int, page_end int,
  pc120_flagged boolean NOT NULL DEFAULT false, text text NOT NULL, tsv tsvector, embedding vector(1024),
  plan_version_id int REFERENCES analytics.plan_versions(id), source_url text NOT NULL, last_verified date NOT NULL);
CREATE INDEX rule_chunks_tsv_gin ON analytics.rule_text_chunks USING gin (tsv);
CREATE INDEX rule_chunks_ref_idx ON analytics.rule_text_chunks (section_ref);

CREATE TABLE analytics.rules (
  id serial PRIMARY KEY, council text NOT NULL, plan_version_id int NOT NULL REFERENCES analytics.plan_versions(id),
  zone text, overlay text, activity text, topic text NOT NULL, parameter text NOT NULL, operator text, value_num numeric, value_text text, unit text,
  applies_if jsonb NOT NULL DEFAULT '{}', status_class text CHECK (status_class IN ('permitted','controlled','restricted_discretionary','discretionary','non_complying','prohibited','standard')),
  standard_ref text, section_ref text NOT NULL, chunk_id int REFERENCES analytics.rule_text_chunks(id), quote text, rule_text text,
  source_url text NOT NULL, last_verified date NOT NULL, evaluable boolean NOT NULL DEFAULT false, notes text);
CREATE INDEX rules_zone_topic_idx ON analytics.rules (zone, topic);

-- Full-text search with citations. rank = ts_rank_cd; zone_filter matches the chapter title (e.g. 'H4' or 'Mixed Housing Suburban').
CREATE OR REPLACE FUNCTION analytics.search_rules(q text, zone_filter text DEFAULT NULL, lim int DEFAULT 8)
RETURNS TABLE (section_ref text, heading text, chapter text, page_start int, snippet text, rank real, source_url text, last_verified date, plan_version text) LANGUAGE sql STABLE AS $$
  SELECT c.section_ref, c.heading, c.chapter, c.page_start,
         ts_headline('english', c.text, websearch_to_tsquery('english', q), 'MaxFragments=2,MaxWords=45,MinWords=15'),
         ts_rank_cd(c.tsv, websearch_to_tsquery('english', q)), c.source_url, c.last_verified, v.version_label
  FROM analytics.rule_text_chunks c JOIN analytics.plan_versions v ON v.id = c.plan_version_id
  WHERE c.tsv @@ websearch_to_tsquery('english', q)
    AND (zone_filter IS NULL OR c.chapter ILIKE '%' || zone_filter || '%' OR c.section_ref ILIKE zone_filter || '.%' OR c.section_ref ILIKE zone_filter)
  ORDER BY 6 DESC LIMIT lim $$;
GRANT USAGE ON SCHEMA analytics TO ai_readonly; GRANT SELECT ON ALL TABLES IN SCHEMA analytics TO ai_readonly;
