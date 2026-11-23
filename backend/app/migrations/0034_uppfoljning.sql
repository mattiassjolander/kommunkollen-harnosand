-- Budget jämfört med utfall per budgetår (#83, kravspec 3.2).
--
-- Reviderad budget, delårsprognos och utfall för årets resultat och per nämnd, med sida i årsredovisningen
-- och delårsrapporten för varje siffra. De läses in från `uppfoljning.json` i budgetårets mapp, bredvid
-- budgetförslagen, och går genom utkast → granskad → publicerad (kravspec 18, ADR-0002). Ingen godkänner det
-- hen själv läst in. Den antagna budgeten hämtas ur årsplanen, som redan finns som antaget budgetförslag.
--
-- `uppgifter` är {arsredovisning, delarsrapport, resultat, namnder}, se `app/uppfoljning.py`. En ny inläsning
-- med samma uppgifter ändrar inget. En ändrad fil ger en ny version av den publicerade (`ersatter_id`).

CREATE TABLE uppfoljning (
    id              bigserial PRIMARY KEY,
    budgetar        integer NOT NULL,
    filnamn         text NOT NULL,
    uppgifter       jsonb NOT NULL,
    status          text NOT NULL CHECK (status IN ('utkast', 'granskad', 'publicerad', 'ersatt', 'aterkallad')),
    redaktorer      text[] NOT NULL,
    skapad          timestamptz NOT NULL DEFAULT now(),
    andrad          timestamptz NOT NULL DEFAULT now(),
    granskad_av     text,
    granskad        timestamptz,
    publicerad_av   text,
    publicerad      timestamptz,
    aterkallad_av   text,
    aterkallad      timestamptz,
    aterkallelse    text,
    ersatter_id     bigint REFERENCES uppfoljning(id) ON DELETE SET NULL,
    andring         text,
    CONSTRAINT uppfoljning_aterkallad CHECK ((status = 'aterkallad') = (aterkallad IS NOT NULL))
);

CREATE INDEX ON uppfoljning (budgetar, status);
CREATE UNIQUE INDEX uppfoljning_en_publicerad ON uppfoljning (budgetar) WHERE status = 'publicerad';
CREATE UNIQUE INDEX uppfoljning_ett_oppet ON uppfoljning (budgetar) WHERE status IN ('utkast', 'granskad');
