-- Diarienummer ur kallelsens föredragningslista (#109).
--
-- Protokollen saknar diarienummer från augusti 2026. Kallelsen, kungörelsen eller handlingarna har dem
-- överst på varje paragrafsida. Föredragningslistan läses en gång per fil (kallelsepunkt), och
-- behandlingar utan diarienummer i protokollet kompletteras när rubriken stämmer
-- (kallelse_diarienummer). Protokollets eget diarienummer går alltid före, och en publicerad
-- rättelse (ADR-0002) går före båda.

-- 'ej_last': inte läst ännu, 'last', 'delvis_fel': delar kunde inte läsas, 'fel': filen kunde inte
-- läsas, 'saknas': filen har ingen föredragningslista.
ALTER TABLE kallelse ADD COLUMN punkter_status text NOT NULL DEFAULT 'ej_last'
    CHECK (punkter_status IN ('ej_last', 'last', 'delvis_fel', 'fel', 'saknas'));
ALTER TABLE kallelse ADD COLUMN punkter_fel jsonb NOT NULL DEFAULT '[]';
ALTER TABLE kallelse ADD COLUMN punkter_lasta timestamptz;

CREATE TABLE kallelsepunkt (
    id              bigserial PRIMARY KEY,
    kallelse_id     bigint NOT NULL REFERENCES kallelse(id) ON DELETE CASCADE,
    ordning         integer NOT NULL,
    paragraf        integer,                    -- kallelsens paragrafnummer, inte alltid protokollets
    rubrik          text NOT NULL,              -- på paragrafsidan, annars i tabellen
    tabellrubrik    text NOT NULL DEFAULT '',
    diarienummer    text[] NOT NULL DEFAULT '{}',
    sida            integer                     -- sidan i PDF:en, för länken
);
CREATE INDEX ON kallelsepunkt (kallelse_id);

-- Kompletteringen, räknad om ur protokollets behandlingar och kallelsepunkterna (app.kallelsepunkter).
CREATE TABLE kallelse_diarienummer (
    sammantrade_id   bigint NOT NULL REFERENCES sammantrade(id) ON DELETE CASCADE,
    paragraf         integer NOT NULL,
    kallelsepunkt_id bigint NOT NULL REFERENCES kallelsepunkt(id) ON DELETE CASCADE,
    diarienummer     text[] NOT NULL,
    PRIMARY KEY (sammantrade_id, paragraf)
);

-- Det som inte stämde mellan kallelsen och protokollet. Skrivs inte över av protokollets tolkning.
ALTER TABLE sammantrade ADD COLUMN kallelse_avvikelser jsonb NOT NULL DEFAULT '[]';
