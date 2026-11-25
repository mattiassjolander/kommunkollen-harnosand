-- Styrande dokument (#63): de PDF:er som kommunen publicerar på sidan Kommunens styrande dokument.
--
-- Ett dokument känns igen på Sitevisions id (`18.<id>` i länken). Får det ett nytt id med samma filnamn i samma
-- kategori som ett dokument som försvann i samma kontroll, är det samma dokument (app.styrande_dokument). En ny fil
-- blir en ny version, och de tidigare versionerna finns kvar med plattformens kopia av filen. Ett dokument som har
-- försvunnit från sidan märks borttaget med datum och sparas.
--
-- Dokumentinformationen (rutan på första sidan) och texten läses när versionen lagras. Uppgifterna återges som de
-- står. Giltigheten räknas när dokumentet läses, eftersom den beror på dagens datum.

CREATE TABLE styrande_dokument (
    id              bigserial PRIMARY KEY,
    sitevision_id   text NOT NULL,           -- det senaste id:t, t.ex. '18.580e43d7163221b2781b73fe'
    url             text NOT NULL,           -- den senaste länken på kommunens sida
    filnamn         text NOT NULL,
    titel           text NOT NULL,           -- filnamnet utan .pdf, som på kommunens sida
    kategorier      text[] NOT NULL,         -- rubrikerna som länken står under
    forst_sedd      timestamptz NOT NULL,
    senast_sedd     timestamptz NOT NULL,
    borttagen       date                     -- när kommunen tog bort dokumentet från sidan
);

CREATE INDEX ON styrande_dokument (sitevision_id);

CREATE TABLE styrande_dokument_version (
    id                  bigserial PRIMARY KEY,
    dokument_id         bigint NOT NULL REFERENCES styrande_dokument(id),
    version             integer NOT NULL,
    url                 text NOT NULL,
    sha256              text NOT NULL,
    storlek             integer NOT NULL,
    innehall            bytea NOT NULL,
    hamtad              timestamptz NOT NULL,
    korning_id          bigint REFERENCES insamlingskorning(id),
    ersatt              timestamptz,         -- när en nyare version hämtades
    sidor               text[] NOT NULL DEFAULT '{}',
    ocr                 boolean NOT NULL DEFAULT false,
    textfel             text,                -- varför texten inte kunde läsas
    dokumentinformation jsonb NOT NULL,      -- rutan på första sidan, fälten som de står (null = saknas)
    UNIQUE (dokument_id, version)
);

-- Rubrikerna på kommunens sida i sidans ordning, för listans filter.
CREATE TABLE styrande_kategori (
    namn     text PRIMARY KEY,
    ordning  integer NOT NULL
);

-- Sökenheten "sida i ett styrande dokument" (#63).
ALTER TABLE sokenhet DROP CONSTRAINT sokenhet_typ_check;
ALTER TABLE sokenhet ADD CONSTRAINT sokenhet_typ_check CHECK (typ IN ('behandling', 'protokollsida', 'budgetforslag',
    'arende', 'ledamot', 'kallelsepunkt', 'styrande_dokument'));
