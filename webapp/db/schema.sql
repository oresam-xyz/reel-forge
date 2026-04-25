CREATE TABLE IF NOT EXISTS users (
    id          SERIAL PRIMARY KEY,
    google_sub  VARCHAR(255) UNIQUE NOT NULL,
    email       VARCHAR(255) NOT NULL,
    name        VARCHAR(255),
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS campaigns (
    id          SERIAL PRIMARY KEY,
    user_id     INTEGER REFERENCES users(id) ON DELETE CASCADE,
    name        VARCHAR(255) NOT NULL,
    brief       JSONB NOT NULL,
    brand_name  VARCHAR(255) NOT NULL,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS auto_approve BOOLEAN DEFAULT FALSE;
ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS visual_model VARCHAR(64) DEFAULT 'kling-2.6-pro';
ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS target_duration INTEGER DEFAULT 30;
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS cost_usd NUMERIC(10,4) DEFAULT 0;
ALTER TABLE users ADD COLUMN IF NOT EXISTS settings JSONB DEFAULT '{}'::jsonb;

DO $$ BEGIN
    CREATE TYPE job_status AS ENUM (
        'pending', 'running', 'review_pending', 'complete', 'failed'
    );
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

CREATE TABLE IF NOT EXISTS jobs (
    id           SERIAL PRIMARY KEY,
    campaign_id  INTEGER REFERENCES campaigns(id) ON DELETE CASCADE,
    angle        TEXT NOT NULL,
    status       job_status DEFAULT 'pending',
    phase        VARCHAR(64),
    project_id   VARCHAR(255),
    output_path  TEXT,
    plan_json    JSONB,
    error        TEXT,
    created_at   TIMESTAMPTZ DEFAULT NOW(),
    updated_at   TIMESTAMPTZ DEFAULT NOW()
);

CREATE OR REPLACE FUNCTION touch_updated_at()
RETURNS TRIGGER AS $$
BEGIN NEW.updated_at = NOW(); RETURN NEW; END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS jobs_updated_at ON jobs;
CREATE TRIGGER jobs_updated_at
    BEFORE UPDATE ON jobs
    FOR EACH ROW EXECUTE FUNCTION touch_updated_at();
