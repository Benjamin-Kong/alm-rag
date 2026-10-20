CREATE TABLE server_policies(server_key TEXT PRIMARY KEY,policy TEXT NOT NULL);
CREATE TABLE server_budgets(server_key TEXT PRIMARY KEY REFERENCES server_policies,tokens REAL NOT NULL,updated_at REAL NOT NULL,next_allowed REAL NOT NULL DEFAULT 0,pause_until REAL NOT NULL DEFAULT 0,failures INTEGER NOT NULL DEFAULT 0,circuit_state TEXT NOT NULL DEFAULT 'CLOSED');
CREATE TABLE request_leases(permit_uid TEXT PRIMARY KEY,server_key TEXT NOT NULL REFERENCES server_budgets,expires REAL NOT NULL);
CREATE INDEX request_lease_server ON request_leases(server_key,expires);
CREATE TABLE credential_blocks(server_key TEXT NOT NULL REFERENCES server_budgets,credential_scope TEXT NOT NULL,error_code TEXT NOT NULL,PRIMARY KEY(server_key,credential_scope));
