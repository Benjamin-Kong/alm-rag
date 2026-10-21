CREATE TABLE operation_snapshots(job_id TEXT PRIMARY KEY REFERENCES jobs(job_id),snapshot TEXT NOT NULL);
CREATE TABLE operation_artifacts(artifact_ref TEXT PRIMARY KEY,project_uid TEXT REFERENCES projects,kind TEXT NOT NULL,sha256 TEXT NOT NULL,size INTEGER NOT NULL,state TEXT NOT NULL,created_at REAL NOT NULL,manifest TEXT NOT NULL);
CREATE TABLE operation_nonces(nonce_hash TEXT PRIMARY KEY,artifact_ref TEXT NOT NULL REFERENCES operation_artifacts,manifest_hash TEXT NOT NULL,actor TEXT NOT NULL,expires_at REAL NOT NULL,used INTEGER NOT NULL DEFAULT 0);
CREATE TABLE operation_backup_schedule(singleton INTEGER PRIMARY KEY CHECK(singleton=1),interval_seconds INTEGER NOT NULL,retention INTEGER NOT NULL,next_due REAL NOT NULL);
