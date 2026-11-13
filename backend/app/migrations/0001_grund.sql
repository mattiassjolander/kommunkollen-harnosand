-- Datagrund: datakällor, mått, insamlingskörningar och observationer.
-- Observationer är append-only: ett värde skrivs aldrig över, en ändring blir en ny version.

CREATE TABLE datakalla (
    id      text PRIMARY KEY,
    titel   text NOT NULL,
    url     text NOT NULL
);

CREATE TABLE matt (
    id                      text PRIMARY KEY,           -- t.ex. 'kolada:N03007'
    datakalla_id            text NOT NULL REFERENCES datakalla(id),
    titel                   text NOT NULL,
    beskrivning             text NOT NULL DEFAULT '',
    enhet                   text NOT NULL,
    kallans_publicering     date,                        -- senaste publicering enligt källan
    uppdaterad              timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE insamlingskorning (
    id          bigserial PRIMARY KEY,
    utlosare    text NOT NULL CHECK (utlosare IN ('manuell', 'schema')),
    startad     timestamptz NOT NULL DEFAULT now(),
    avslutad    timestamptz,
    status      text NOT NULL DEFAULT 'pagar'
);

CREATE TABLE kallkorning (
    korning_id      bigint NOT NULL REFERENCES insamlingskorning(id),
    datakalla_id    text NOT NULL REFERENCES datakalla(id),
    status          text NOT NULL,
    antal_nya       integer NOT NULL DEFAULT 0,
    antal_andrade   integer NOT NULL DEFAULT 0,
    antal_oforandrade integer NOT NULL DEFAULT 0,
    fel             text,
    startad         timestamptz NOT NULL,
    avslutad        timestamptz,
    PRIMARY KEY (korning_id, datakalla_id)
);

CREATE TABLE observation (
    id                  bigserial PRIMARY KEY,
    matt_id             text NOT NULL REFERENCES matt(id),
    omrade              text NOT NULL,                   -- t.ex. kommunkod '2280'
    period              text NOT NULL,                   -- avsedd period, t.ex. '2025'
    varde               numeric,
    kallans_publicering date,
    hamtad              timestamptz NOT NULL,
    version             integer NOT NULL,
    korning_id          bigint NOT NULL REFERENCES insamlingskorning(id),
    UNIQUE (matt_id, omrade, period, version)
);
