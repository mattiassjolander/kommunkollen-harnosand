-- Ledamotsregister (#30). En ledamot identifieras på namn, så varje namn som förekommer i en
-- närvarolista får en rad. Partitillhörighet, roll och tjänstgöring finns per sammanträde i
-- narvaro (ADR-0004) och dupliceras inte här.
--
-- En redaktör kan slå ihop två namn som är samma person: namnet pekar då på huvudnamnet
-- (huvud_id). En uppdelning tar bort pekaren. Båda loggas i ledamot_handelse.

CREATE TABLE ledamot (
    id       bigserial PRIMARY KEY,
    namn     text NOT NULL UNIQUE,
    huvud_id bigint REFERENCES ledamot(id),
    CHECK (huvud_id IS NULL OR huvud_id <> id)
);

CREATE TABLE ledamot_handelse (
    id                bigserial PRIMARY KEY,
    typ               text NOT NULL CHECK (typ IN ('sammanslagning', 'uppdelning')),
    ledamot_id        bigint NOT NULL REFERENCES ledamot(id),  -- namnet som flyttades
    huvud_id          bigint REFERENCES ledamot(id),           -- ny huvudperson, NULL vid uppdelning
    tidigare_huvud_id bigint REFERENCES ledamot(id),
    redaktor          text NOT NULL,
    tid               timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX narvaro_namn ON narvaro (namn);

INSERT INTO ledamot (namn)
SELECT DISTINCT namn FROM narvaro WHERE kategori <> 'ovrig'
ON CONFLICT DO NOTHING;
