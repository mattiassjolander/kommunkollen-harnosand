-- Protokollavvikelser (#47): uppgifter i ett protokoll som inte stämmer med varandra, att anmäla till kommunen.
--
-- Kontrollerna (`app/protokollkontroller.py`) körs vid varje tolkning och omtolkning. En avvikelse identifieras
-- av `nyckel` inom sammanträdet, så att redaktörens status bevaras när protokollet tolkas om. En avvikelse som
-- inte längre hittas tas bort om ingen har satt någon status, och sparas annars med `hittas = false`.
-- `atgardad_dokument_id` är protokollets nya version när avvikelsen försvann därför att kommunen publicerade
-- protokollet på nytt (Reviderad av källan, docs/design.md).
--
-- Status sätts av en redaktör: ny, anmäld till kommunen, rättad av kommunen eller inte ett fel, med datum och
-- anteckning. Varje ändring sparas i `protokollavvikelse_status`.

CREATE TABLE protokollavvikelse (
    id                    bigserial PRIMARY KEY,
    sammantrade_id        bigint NOT NULL REFERENCES sammantrade(id) ON DELETE CASCADE,
    typ                   text NOT NULL CHECK (typ IN ('rostsumma', 'parti_olika', 'ersattare', 'paragrafnummer',
                                                       'parti_saknas', 'stavning')),
    nyckel                text NOT NULL,
    paragraf              integer,
    sida                  integer,
    text                  text NOT NULL,
    dokument_id           bigint NOT NULL REFERENCES dokument(id),
    hittad                timestamptz NOT NULL,
    hittas                boolean NOT NULL DEFAULT true,
    atgardad_dokument_id  bigint REFERENCES dokument(id),
    status                text NOT NULL DEFAULT 'ny' CHECK (status IN ('ny', 'anmald', 'rattad', 'inte_fel')),
    statusdatum           date,
    anteckning            text,
    status_satt_av        text,
    status_satt           timestamptz,
    UNIQUE (sammantrade_id, nyckel)
);

CREATE INDEX ON protokollavvikelse (status);

CREATE TABLE protokollavvikelse_status (
    id                    bigserial PRIMARY KEY,
    protokollavvikelse_id bigint NOT NULL REFERENCES protokollavvikelse(id) ON DELETE CASCADE,
    status                text NOT NULL,
    statusdatum           date NOT NULL,
    anteckning            text,
    satt_av               text NOT NULL,
    satt                  timestamptz NOT NULL DEFAULT now()
);
