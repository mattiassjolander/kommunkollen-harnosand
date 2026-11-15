-- Ärendespårning (#32, ADR-0003). Ett ärende är plattformens egen entitet. Behandlingar i olika
-- organ kopplas till samma ärende via diarienummer eller via hänvisningar i beslutsunderlaget.
--
-- Behandlingar tas bort och tolkas om när protokollet ändras, men sammanträdet behåller sitt id.
-- Kopplingar och ärendetillhörighet pekar därför ut behandlingen med sammanträde och paragraf.

CREATE TABLE hanvisning (
    id              bigserial PRIMARY KEY,
    behandling_id   bigint NOT NULL REFERENCES behandling(id) ON DELETE CASCADE,
    ordning         integer NOT NULL,
    organ           text,                            -- NULL när hänvisningen inte anger organet
    datum           date NOT NULL,
    paragraf        integer NOT NULL,
    text            text NOT NULL                    -- som det står i beslutsunderlaget
);

-- En koppling mellan två behandlingar i samma ärende. `fran` är den tidigare behandlingen.
-- Automatiska kopplingar och förslag räknas om efter varje tolkning. En redaktörs beslut
-- (bekräftad eller avvisad) står kvar.
CREATE TABLE koppling (
    id                  bigserial PRIMARY KEY,
    fran_sammantrade_id bigint NOT NULL REFERENCES sammantrade(id) ON DELETE CASCADE,
    fran_paragraf       integer NOT NULL,
    till_sammantrade_id bigint NOT NULL REFERENCES sammantrade(id) ON DELETE CASCADE,
    till_paragraf       integer NOT NULL,
    grund               text NOT NULL CHECK (grund IN ('diarienummer', 'hanvisning')),
    underlag            text NOT NULL,               -- diarienumret eller hänvisningens text
    status              text NOT NULL CHECK (status IN ('automatisk', 'forslag', 'bekraftad', 'avvisad')),
    redaktor            text,
    beslutad            timestamptz,
    skapad              timestamptz NOT NULL DEFAULT now(),
    UNIQUE (fran_sammantrade_id, fran_paragraf, till_sammantrade_id, till_paragraf)
);

CREATE TABLE arende (
    id      bigserial PRIMARY KEY,
    skapad  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE arende_behandling (
    sammantrade_id  bigint NOT NULL REFERENCES sammantrade(id) ON DELETE CASCADE,
    paragraf        integer NOT NULL,
    arende_id       bigint NOT NULL REFERENCES arende(id),
    PRIMARY KEY (sammantrade_id, paragraf)
);

CREATE INDEX ON hanvisning (behandling_id);
CREATE INDEX ON koppling (till_sammantrade_id, till_paragraf);
CREATE INDEX ON koppling (status);
CREATE INDEX ON arende_behandling (arende_id);
