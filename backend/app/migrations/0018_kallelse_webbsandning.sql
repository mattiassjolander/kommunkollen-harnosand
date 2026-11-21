-- Kallelser och webbsändningar till sammanträdena (#68, del 3).
--
-- De kopplas till sammanträdena när de läses: samma organ och datum, och närmaste klockslag när
-- det finns (fullmäktige hade två sammanträden 2026-10-26 med var sin kungörelse). En kallelse som
-- byts ut får en ny adress på harnosand.se och blir en ny rad.
CREATE TABLE kallelse (
    id          bigserial PRIMARY KEY,
    organ       text NOT NULL,
    datum       date NOT NULL,
    tid         text,
    typ         text NOT NULL CHECK (typ IN ('kungorelse', 'kallelse', 'handlingar')),
    titel       text NOT NULL,
    url         text NOT NULL UNIQUE,
    storlek     bigint,
    plats       text,           -- ur kallelsen, när den stod där
    pdf_last    boolean NOT NULL DEFAULT false,
    forst_sedd  timestamptz NOT NULL,
    senast_sedd timestamptz NOT NULL,
    korning_id  bigint REFERENCES insamlingskorning(id)
);
CREATE INDEX ON kallelse (organ, datum);

CREATE TABLE webbsandning (
    id          bigserial PRIMARY KEY,
    organ       text NOT NULL,
    datum       date NOT NULL,
    url         text NOT NULL UNIQUE,
    titel       text NOT NULL,
    forst_sedd  timestamptz NOT NULL,
    senast_sedd timestamptz NOT NULL,
    korning_id  bigint REFERENCES insamlingskorning(id)
);
CREATE INDEX ON webbsandning (organ, datum);
