-- Redaktionella rättelser av automatiskt tolkade uppgifter (#33).
--
-- En rättelse ligger bredvid tolkningen och ändrar den inte. Den läggs på när uppgiften läses,
-- så en ny insamling eller omtolkning kan inte skriva över den. Uppgiften pekas ut med
-- sammanträde och paragraf (och namn och votering för en röst), eftersom behandlingarna skapas
-- om när protokollen tolkas om.
--
-- Statusflöde: utkast → granskad → publicerad. En utgivare som inte skrev rättelsen granskar och
-- publicerar den. En ny publicerad rättelse av samma uppgift ersätter den tidigare.

CREATE TABLE rattelse (
    id              bigserial PRIMARY KEY,
    sammantrade_id  bigint NOT NULL REFERENCES sammantrade(id) ON DELETE CASCADE,
    objekt          text NOT NULL CHECK (objekt IN ('behandling', 'rost', 'narvaro')),
    paragraf        integer,                         -- behandling och röst
    votering        integer,                         -- röst: voteringens nummer i behandlingen
    namn            text NOT NULL DEFAULT '',        -- röst och närvaro: namnet som i protokollet
    falt            text NOT NULL,
    ursprungligt    jsonb,                           -- tolkningens värde när rättelsen skrevs
    nytt            jsonb,
    motivering      text NOT NULL,
    status          text NOT NULL CHECK (status IN ('utkast', 'granskad', 'publicerad', 'ersatt')),
    redaktor        text NOT NULL,
    skapad          timestamptz NOT NULL DEFAULT now(),
    granskad_av     text,
    granskad        timestamptz,
    publicerad_av   text,
    publicerad      timestamptz,
    CHECK (
        (objekt = 'behandling' AND paragraf IS NOT NULL AND falt IN ('rubrik', 'beslut', 'diarienummer'))
        OR (objekt = 'rost' AND paragraf IS NOT NULL AND votering IS NOT NULL AND namn <> '' AND falt IN ('rost', 'parti'))
        OR (objekt = 'narvaro' AND namn <> '' AND falt = 'parti')
    )
);

CREATE INDEX ON rattelse (sammantrade_id);
CREATE INDEX ON rattelse (status);
CREATE UNIQUE INDEX rattelse_en_publicerad ON rattelse (sammantrade_id, objekt, coalesce(paragraf, -1),
    coalesce(votering, -1), namn, falt) WHERE status = 'publicerad';
