CREATE TABLE IF NOT EXISTS requests (
  id TEXT PRIMARY KEY,
  created_at TEXT NOT NULL,
  server TEXT NOT NULL,
  tool TEXT NOT NULL,
  arguments_json TEXT NOT NULL,
  arguments_hash TEXT NOT NULL,
  actor TEXT,
  env TEXT,
  status TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS decisions (
  id TEXT PRIMARY KEY,
  request_id TEXT NOT NULL,
  decided_at TEXT NOT NULL,
  decision TEXT NOT NULL,
  matched_policy_id TEXT,
  matched_condition TEXT,
  reason TEXT,
  FOREIGN KEY(request_id) REFERENCES requests(id)
);

CREATE TABLE IF NOT EXISTS events (
  id TEXT PRIMARY KEY,
  created_at TEXT NOT NULL,
  request_id TEXT,
  type TEXT NOT NULL,
  data_json TEXT NOT NULL,
  FOREIGN KEY(request_id) REFERENCES requests(id)
);
