-- Motstridigheter i styrande dokument (#151): motsägelser, felaktiga hänvisningar och flera gällande versioner.
--
-- Förslagen kommer från insamlingen (maskinella kandidater till flera gällande versioner) eller från skillen
-- `harnosandskollen-styrande-dokument`, som en redaktör kör (ADR-0009). De går från utkast via granskad till
-- publicerad, som rättelser, och ingen godkänner ett förslag som hen själv har läst in. Ett förslag som inte håller
-- avvisas. En publicerad motstridighet kan återkallas.
--
-- `nyckel` identifierar förslaget, så att samma förslag inte läses in två gånger. `citat` är ställena i dokumenten,
-- {dokument_id, version, sida, paragraf, text}. `uppgift` är den kontrollerbara uppgiften om det som finns, för en
-- felaktig hänvisning. `versioner` är versionen av varje berört dokument när förslaget togs fram, eller när en
-- redaktör senast tog ställning. `dokument_andrat` sätts när ett berört dokument får en ny version.
--
-- En publicerad motstridighet har status ny, anmäld till kommunen eller åtgärdad av kommunen, som en redaktör
-- sätter med datum. Varje ändring sparas i `motstridighet_status`.

CREATE TABLE motstridighet (
    id              bigserial PRIMARY KEY,
    typ             text NOT NULL CHECK (typ IN ('motsagelse', 'felaktig_hanvisning', 'flera_versioner')),
    nyckel          text NOT NULL UNIQUE,
    forklaring      text NOT NULL,
    citat           jsonb NOT NULL DEFAULT '[]',
    uppgift         jsonb,
    dokument_ids    bigint[] NOT NULL,
    versioner       jsonb NOT NULL,
    kalla           text NOT NULL CHECK (kalla IN ('insamling', 'skill')),
    grund           text,
    status          text NOT NULL DEFAULT 'utkast'
                    CHECK (status IN ('utkast', 'granskad', 'publicerad', 'avvisad', 'aterkallad')),
    redaktorer      text[] NOT NULL DEFAULT '{}',
    skapad          timestamptz NOT NULL,
    granskad_av     text,
    granskad        timestamptz,
    publicerad_av   text,
    publicerad      timestamptz,
    avvisad_av      text,
    avvisad         timestamptz,
    avvisning       text,
    aterkallad_av   text,
    aterkallad      timestamptz,
    aterkallelse    text,
    anmalan         text NOT NULL DEFAULT 'ny' CHECK (anmalan IN ('ny', 'anmald', 'atgardad')),
    anmalan_datum   date,
    anteckning      text,
    dokument_andrat date
);

CREATE INDEX ON motstridighet USING gin (dokument_ids);
CREATE INDEX ON motstridighet (status);

CREATE TABLE motstridighet_status (
    id               bigserial PRIMARY KEY,
    motstridighet_id bigint NOT NULL REFERENCES motstridighet(id) ON DELETE CASCADE,
    status           text NOT NULL,
    statusdatum      date NOT NULL,
    anteckning       text,
    satt_av          text NOT NULL,
    satt             timestamptz NOT NULL DEFAULT now()
);
