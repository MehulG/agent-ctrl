ALTER TABLE requests ADD COLUMN risk_score INTEGER;
ALTER TABLE requests ADD COLUMN approved_at TEXT;
ALTER TABLE requests ADD COLUMN approved_by TEXT;
ALTER TABLE requests ADD COLUMN risk_mode TEXT;

-- optional, but useful
ALTER TABLE decisions ADD COLUMN risk_score INTEGER;
