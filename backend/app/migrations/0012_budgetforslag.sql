-- Partiernas budgetförslag (#48, kravspec 17A).
--
-- Ett budgetförslag gäller ett budgetår och läses in från `data/budgetforslag/<budgetår>/`, där
-- `budget.json` beskriver varje förslag med siffror och sidhänvisningar. Originalet (PDF eller Word)
-- lagras som källa. Siffrorna är uppgifter ur dokumentet och går genom utkast → granskad →
-- publicerad (kravspec 18). Ingen godkänner ett förslag som hen själv läst in eller ändrat.
--
-- `inlast` är uppgifterna som de lästes in och `uppgifter` det som gäller efter redaktörens
-- ändringar. En ny inläsning med samma `inlast` ändrar inget.

CREATE TABLE budgetforslag (
    id              bigserial PRIMARY KEY,
    budgetar        integer NOT NULL,
    nyckel          text NOT NULL,                   -- filnamnet utan ändelse, t.ex. 'L+M' eller 'S-tillagg'
    partier         text[] NOT NULL,                 -- partiförkortningar i alfabetisk ordning
    titel           text NOT NULL,
    typ             text NOT NULL CHECK (typ IN ('budget', 'tillagg')),
    antagen         boolean NOT NULL DEFAULT false,  -- det förslag som kommunfullmäktige antog
    filnamn         text NOT NULL,
    sha256          text NOT NULL,
    original        bytea NOT NULL,
    inlast          jsonb NOT NULL,
    uppgifter       jsonb NOT NULL,                  -- {skattesats, resultat[], ramar[]} med sidor
    anmarkning      text NOT NULL DEFAULT '',
    status          text NOT NULL CHECK (status IN ('utkast', 'granskad', 'publicerad', 'ersatt')),
    redaktorer      text[] NOT NULL,                 -- den som läste in och de som ändrat
    skapad          timestamptz NOT NULL DEFAULT now(),
    andrad          timestamptz NOT NULL DEFAULT now(),
    granskad_av     text,
    granskad        timestamptz,
    publicerad_av   text,
    publicerad      timestamptz
);

CREATE INDEX ON budgetforslag (budgetar, status);
CREATE UNIQUE INDEX budgetforslag_en_publicerad ON budgetforslag (budgetar, nyckel) WHERE status = 'publicerad';
CREATE UNIQUE INDEX budgetforslag_ett_oppet ON budgetforslag (budgetar, nyckel) WHERE status IN ('utkast', 'granskad');
