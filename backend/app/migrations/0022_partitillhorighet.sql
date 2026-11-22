-- Fastställd partitillhörighet per period (#100, ADR-0006). En persons parti under en period, fastställt av
-- redaktionen och godkänt av en utgivare. Den gäller alla förekomster av personen (alla ihopslagna namn) vid
-- sammanträden inom perioden, före protokollets uppgift och det härledda partiet men efter en rättelse av en
-- enskild förekomst. Personen pekas ut med ett namn i ledamotsregistret, och personen är huvudnamnets id.
CREATE TABLE partitillhorighet (
    id            bigserial PRIMARY KEY,
    ledamot_id    bigint NOT NULL REFERENCES ledamot(id),
    parti         text NOT NULL,                     -- förkortning, '-' för partilös
    fran          date NOT NULL,
    till          date,                              -- NULL: tills vidare
    motivering    text NOT NULL,
    status        text NOT NULL CHECK (status IN ('utkast', 'granskad', 'publicerad', 'ersatt', 'aterkallad')),
    ersatter_id   bigint REFERENCES partitillhorighet(id) ON DELETE SET NULL,
    redaktor      text NOT NULL,
    skapad        timestamptz NOT NULL DEFAULT now(),
    granskad_av   text,
    granskad      timestamptz,
    publicerad_av text,
    publicerad    timestamptz,
    aterkallad_av text,
    aterkallad    timestamptz,
    aterkallelse  text,
    CHECK (till IS NULL OR till >= fran),
    CHECK ((status = 'aterkallad') = (aterkallad IS NOT NULL))
);

CREATE INDEX ON partitillhorighet (ledamot_id) WHERE status = 'publicerad';
