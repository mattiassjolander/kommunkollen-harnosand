-- Yrkanden, propositionsordning, voteringar och reservationer vid en behandling (#31).
--
-- Automatiskt tolkade uppgifter ur protokollet, som tas bort och tolkas om tillsammans med
-- behandlingen. En röst står som den står i voteringslistan och räknas aldrig fram.

ALTER TABLE behandling ADD COLUMN propositionsordning text;

CREATE TABLE yrkande (
    id              bigserial PRIMARY KEY,
    behandling_id   bigint NOT NULL REFERENCES behandling(id) ON DELETE CASCADE,
    ordning         integer NOT NULL,
    text            text NOT NULL,
    personer        jsonb NOT NULL DEFAULT '[]'      -- [{"namn": …, "parti": …}]
);

CREATE TABLE reservation (
    id              bigserial PRIMARY KEY,
    behandling_id   bigint NOT NULL REFERENCES behandling(id) ON DELETE CASCADE,
    ordning         integer NOT NULL,
    text            text NOT NULL,
    personer        jsonb NOT NULL DEFAULT '[]',     -- de som står med namn
    partier         text[] NOT NULL DEFAULT '{}'      -- "Sverigedemokraterna reserverar sig" → SD
);

CREATE TABLE votering (
    id              bigserial PRIMARY KEY,
    behandling_id   bigint NOT NULL REFERENCES behandling(id) ON DELETE CASCADE,
    ordning         integer NOT NULL,
    ja_forslag      text,
    nej_forslag     text,
    -- Siffrorna som protokollets text anger. NULL när texten inte anger dem.
    ja              integer,
    nej             integer,
    avstar          integer,
    franvarande     integer,
    resultat        text,                            -- ordförandens konstaterande
    vinnare         text CHECK (vinnare IN ('ja', 'nej'))
);

CREATE TABLE rost (
    id              bigserial PRIMARY KEY,
    votering_id     bigint NOT NULL REFERENCES votering(id) ON DELETE CASCADE,
    ordning         integer NOT NULL,
    namn            text,                            -- NULL för en tom stol utan namn
    parti           text,
    rost            text NOT NULL CHECK (rost IN ('ja', 'nej', 'avstar', 'franvarande')),
    ersatt          text,                            -- ledamoten som en tjänstgörande ersättare röstade för
    ersatt_parti    text
);

CREATE INDEX ON yrkande (behandling_id);
CREATE INDEX ON reservation (behandling_id);
CREATE INDEX ON votering (behandling_id);
CREATE INDEX ON rost (votering_id);
CREATE INDEX ON rost (namn);
