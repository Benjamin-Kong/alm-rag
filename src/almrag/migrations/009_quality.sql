CREATE TABLE quality_datasets(dataset_ref TEXT PRIMARY KEY,project_uid TEXT NOT NULL REFERENCES projects,payload TEXT NOT NULL,sha256 TEXT NOT NULL,case_count INTEGER NOT NULL,created_at REAL NOT NULL);
CREATE TABLE quality_requests(job_id TEXT PRIMARY KEY REFERENCES jobs(job_id),snapshot TEXT NOT NULL,snapshot_hash TEXT NOT NULL);
CREATE TABLE quality_reports(job_id TEXT PRIMARY KEY REFERENCES jobs(job_id),project_uid TEXT NOT NULL REFERENCES projects,stage TEXT NOT NULL,status TEXT NOT NULL CHECK(status IN ('PASS','FAIL','NOT VERIFIED')),report TEXT NOT NULL);
CREATE TRIGGER quality_request_immutable BEFORE UPDATE ON quality_requests BEGIN SELECT RAISE(ABORT,'quality request immutable'); END;
CREATE TRIGGER quality_dataset_immutable BEFORE UPDATE ON quality_datasets BEGIN SELECT RAISE(ABORT,'quality dataset immutable'); END;
CREATE TRIGGER quality_report_owner_insert BEFORE INSERT ON quality_reports WHEN NOT EXISTS(SELECT 1 FROM jobs WHERE job_id=NEW.job_id AND project_uid=NEW.project_uid AND stage=NEW.stage AND stage IN ('INTEGRITY','EVALUATE')) BEGIN SELECT RAISE(ABORT,'quality report ownership mismatch'); END;
