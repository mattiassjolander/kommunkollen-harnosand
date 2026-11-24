-- Sökindex för fritextsökning (#142, kravspec: "Dokument ska indexeras och göras sökbara").
--
-- En sökenhet är det som en träff visar: en behandling, en sida i ett protokoll, en sida i ett
-- budgetförslag, ett ärende, en ledamot eller en punkt i en kallelse. Varje enhet har en typ, en
-- nyckel inom typen, en länk till sin sida på plattformen och, när den finns, en sida i källdokumentet.
-- Enheten innehåller den gällande versionen: publicerade rättelser är pålagda (app.sokindex).
--
-- Texten ligger i tre viktklasser: `text_a` (rubrik och diarienummer), `text_b` (beslut och yrkanden)
-- och `text_c` (löptext). Sökvektorn räknas ur dem med den svenska konfigurationen. `sha256` är
-- hashen av texten, så att bara ändrade enheter räknas om, och `text_andrad` när texten senast
-- ändrades. Del 2 (#69) lägger en vektorkolumn bredvid och räknar om den när `text_andrad` är nyare.

CREATE TABLE sokenhet (
    id              bigserial PRIMARY KEY,
    typ             text NOT NULL CHECK (typ IN ('behandling', 'protokollsida', 'budgetforslag', 'arende',
                                                 'ledamot', 'kallelsepunkt')),
    nyckel          text NOT NULL,                  -- identifierar enheten inom typen, t.ex. '12:5'
    sammantrade_id  bigint REFERENCES sammantrade(id) ON DELETE CASCADE,
    rubrik          text NOT NULL,
    undertitel      text,                           -- t.ex. '§ 5' eller 'Kallelse'
    organ           text,
    datum           date,
    ar              integer,                        -- för filtret: sammanträdets år, budgetåret
    lank            text NOT NULL,                  -- sidan på plattformen
    dokument        text,                           -- källdokumentet, med #page= när sidan är känd
    sida            integer,
    markeringar     text[] NOT NULL DEFAULT '{}',   -- t.ex. 'automatiskt_tolkad', 'rattad', 'ocr'
    exakt           text[] NOT NULL DEFAULT '{}',   -- diarienummer och namn, gemener, för exakta frågor
    text_a          text NOT NULL DEFAULT '',
    text_b          text NOT NULL DEFAULT '',
    text_c          text NOT NULL DEFAULT '',
    sokvektor       tsvector GENERATED ALWAYS AS (
                        setweight(to_tsvector('swedish', text_a), 'A')
                        || setweight(to_tsvector('swedish', text_b), 'B')
                        || setweight(to_tsvector('swedish', text_c), 'D')) STORED,
    sha256          text NOT NULL,
    text_andrad     timestamptz NOT NULL DEFAULT now(),
    andrad          timestamptz NOT NULL DEFAULT now(),
    UNIQUE (typ, nyckel)
);

CREATE INDEX sokenhet_sokvektor ON sokenhet USING gin (sokvektor);
CREATE INDEX sokenhet_exakt ON sokenhet USING gin (exakt);
CREATE INDEX ON sokenhet (sammantrade_id);
CREATE INDEX ON sokenhet (datum);

-- Dokumentens text sida för sida, läst en gång per dokumentversion (dokument är append-only).
-- `ocr` när sidorna lästs med OCR. Ett dokument som inte gick att läsa får inga sidor och `fel`.
CREATE TABLE dokumenttext (
    dokument_id     bigint PRIMARY KEY REFERENCES dokument(id) ON DELETE CASCADE,
    sidor           text[] NOT NULL,
    ocr             boolean NOT NULL DEFAULT false,
    fel             text,
    last            timestamptz NOT NULL DEFAULT now()
);

-- En ombyggnad av hela indexet (python -m app.sokindex --bygg-om). Den kan avbrytas och återupptas:
-- det som lästs eller skrivits efter `startad` görs inte om. `klar` när den gått igenom.
CREATE TABLE sokindex_ombyggnad (
    id              bigserial PRIMARY KEY,
    startad         timestamptz NOT NULL DEFAULT now(),
    klar            timestamptz
);
