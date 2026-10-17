-- Final privilege pass for the agent's read-only role. Default privileges and blanket grants give it SELECT on every core table; the chat history is the one table it must not read.
DO $$ BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='ai_readonly') AND to_regclass('core.user_chat') IS NOT NULL THEN REVOKE ALL ON core.user_chat FROM ai_readonly; END IF;
END $$;
