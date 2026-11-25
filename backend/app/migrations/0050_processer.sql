-- Processer ur reglementen och delegationsordningar (#152).
--
-- En process är en arbetsgång som redaktionen har valt att beskriva (GLOSSARY.md). Redaktionen bestämmer listan:
-- en redaktör lägger till en process, och skillen `harnosandskollen-styrande-dokument` fyller i stegen (ADR-0009).
-- Processen går som en helhet, med alla sina steg, från utkast via granskad till publicerad (ADR-0002). Ingen
-- godkänner en process som hen själv har lagt till eller läst in steg i (`redaktorer`). En process som inte ska
-- beskrivas avvisas. En publicerad process kan återkallas.
--
-- Ett steg anger vem som gör något, vad som görs, när eller inom vilken tidsfrist (om dokumentet anger det) och
-- källan: ett ordagrant citat med dokument, version, sida och paragraf. `dokument_andrat` sätts när dokumentet får
-- en ny version, tills en redaktör har tagit ställning. Processen förblir publicerad.
--
-- `stegnyckel` identifierar de inlästa stegen, så att samma fil inte läses in två gånger.

CREATE TABLE process (
    id             bigserial PRIMARY KEY,
    namn           text NOT NULL,
    beskrivning    text,
    ordning        integer NOT NULL,
    status         text NOT NULL DEFAULT 'utkast'
                   CHECK (status IN ('utkast', 'granskad', 'publicerad', 'avvisad', 'aterkallad')),
    redaktorer     text[] NOT NULL DEFAULT '{}',
    skapad         timestamptz NOT NULL DEFAULT now(),
    skapad_av      text,
    stegnyckel     text,
    steg_inlasta   timestamptz,
    granskad_av    text,
    granskad       timestamptz,
    publicerad_av  text,
    publicerad     timestamptz,
    avvisad_av     text,
    avvisad        timestamptz,
    avvisning      text,
    aterkallad_av  text,
    aterkallad     timestamptz,
    aterkallelse   text
);

CREATE UNIQUE INDEX ON process (lower(namn));

CREATE TABLE process_steg (
    id              bigserial PRIMARY KEY,
    process_id      bigint NOT NULL REFERENCES process(id) ON DELETE CASCADE,
    ordning         integer NOT NULL,
    vem             text NOT NULL,
    vad             text NOT NULL,
    nar             text,
    dokument_id     bigint NOT NULL REFERENCES styrande_dokument(id),
    version         integer NOT NULL,
    sida            integer NOT NULL,
    paragraf        text NOT NULL,
    citat           text NOT NULL,
    dokument_andrat date,
    UNIQUE (process_id, ordning)
);

CREATE INDEX ON process_steg (dokument_id);

-- Den första listan. Stegen läses in av skillen.
INSERT INTO process (namn, ordning) VALUES
    ('Kallelse till sammanträde', 1),
    ('Justering av protokoll', 2),
    ('Motion', 3),
    ('Medborgarförslag', 4),
    ('Anmälan av delegationsbeslut', 5),
    ('Budgetprocessen', 6);
