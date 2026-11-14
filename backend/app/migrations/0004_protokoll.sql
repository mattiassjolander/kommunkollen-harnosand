-- Protokoll: dokumenten som hämtats och det som tolkats ur dem.
--
-- Dokument är append-only: nytt innehåll under samma adress blir en ny version, och den
-- tidigare finns kvar. Sammanträden, närvaro och behandlingar är automatiskt tolkade uppgifter
-- ur den senaste versionen av sammanträdets protokoll, och tolkas om när protokollet ändras.

CREATE TABLE dokument (
    id              bigserial PRIMARY KEY,
    datakalla_id    text NOT NULL REFERENCES datakalla(id),
    url             text NOT NULL,
    version         integer NOT NULL,
    filnamn         text NOT NULL,
    typ             text NOT NULL,                  -- 'protokoll'
    organ           text NOT NULL,                  -- t.ex. 'KF'
    sha256          text NOT NULL,
    storlek         integer NOT NULL,
    innehall        bytea NOT NULL,                 -- plattformens egen kopia
    hamtad          timestamptz NOT NULL,
    korning_id      bigint NOT NULL REFERENCES insamlingskorning(id),
    UNIQUE (url, version)
);

CREATE TABLE sammantrade (
    id              bigserial PRIMARY KEY,
    organ           text NOT NULL,
    -- Identifierar sammanträdet inom organet: datum, och starttid när den finns
    -- (ett organ kan sammanträda två gånger samma dag).
    nyckel          text NOT NULL,
    datum           date,                           -- NULL när protokollet inte gick att tolka och filnamnet saknar datum
    starttid        text,
    sluttid         text,
    plats           text,
    dokument_id     bigint NOT NULL REFERENCES dokument(id),
    tolkning        text NOT NULL CHECK (tolkning IN ('tolkad', 'ej_tolkad')),
    avvikelser      jsonb NOT NULL DEFAULT '[]',
    tolkad          timestamptz NOT NULL,
    UNIQUE (organ, nyckel)
);

CREATE TABLE narvaro (
    id                  bigserial PRIMARY KEY,
    sammantrade_id      bigint NOT NULL REFERENCES sammantrade(id) ON DELETE CASCADE,
    ordning             integer NOT NULL,
    namn                text NOT NULL,
    parti               text,                       -- som protokollet anger. '-' = partilös, NULL = anges inte
    roll                text,
    kategori            text NOT NULL CHECK (kategori IN ('beslutande', 'ej_tjanstgorande', 'franvarande', 'ovrig')),
    tjanstgor_for       text,
    tjanstgor_for_parti text,
    paragrafer          integer[],                  -- NULL = hela sammanträdet
    jav                 integer[] NOT NULL DEFAULT '{}'
);

CREATE TABLE behandling (
    id              bigserial PRIMARY KEY,
    sammantrade_id  bigint NOT NULL REFERENCES sammantrade(id) ON DELETE CASCADE,
    ordning         integer NOT NULL,
    paragraf        integer NOT NULL,
    rubrik          text NOT NULL,
    diarienummer    text[] NOT NULL DEFAULT '{}',
    beslut          text
);

CREATE INDEX ON dokument (url);
CREATE INDEX ON narvaro (sammantrade_id);
CREATE INDEX ON behandling (sammantrade_id);
CREATE INDEX ON sammantrade (organ, datum);
