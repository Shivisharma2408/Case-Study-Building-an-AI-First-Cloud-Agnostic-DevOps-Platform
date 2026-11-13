-- 001: the ideas table.
CREATE TABLE IF NOT EXISTS ideas (
    id         BIGSERIAL PRIMARY KEY,
    content    TEXT        NOT NULL CHECK (char_length(btrim(content)) BETWEEN 1 AND 10000),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ideas_created_at_idx ON ideas (created_at DESC);
