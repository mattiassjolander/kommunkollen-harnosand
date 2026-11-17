-- Gemensamma planförutsättningar per budgetår (#58).
--
-- Alla budgetförslag för ett budgetår utgår från samma planförutsättningar: ramar per organ,
-- skattesats, resultat-, investerings- och balansbudget samt förenklad kassaflödesanalys. De läses
-- in från en Excelfil med en flik per budgetår och går genom utkast → granskad → publicerad
-- (kravspec 18, ADR-0002). Ingen godkänner det hen själv läst in.
--
-- `uppgifter` är {skattesats: {procent, kalla}, tabeller: {resultatbudget, namnder, investeringar,
-- balansbudget, kassaflode}}, där varje tabell är en lista med {post, mnkr, kalla}. En ny inläsning
-- med samma uppgifter ändrar inget.
--
-- Budgetförslagens `uppgifter` gäller från och med nu bara budgetåret: {skattesats: {ore} (förändring
-- mot planförutsättningen, eller {procent} för ett år utan planförutsättningar), resultat: {procent},
-- ramar: [{organ, mnkr}]}, med sidor. Befintliga förslag förs över av `python -m app.budgetforslag`.

CREATE TABLE planforutsattningar (
    id              bigserial PRIMARY KEY,
    budgetar        integer NOT NULL,
    filnamn         text NOT NULL,
    uppgifter       jsonb NOT NULL,
    status          text NOT NULL CHECK (status IN ('utkast', 'granskad', 'publicerad', 'ersatt')),
    redaktorer      text[] NOT NULL,                 -- den som läste in
    skapad          timestamptz NOT NULL DEFAULT now(),
    andrad          timestamptz NOT NULL DEFAULT now(),
    granskad_av     text,
    granskad        timestamptz,
    publicerad_av   text,
    publicerad      timestamptz
);

CREATE INDEX ON planforutsattningar (budgetar, status);
CREATE UNIQUE INDEX planforutsattningar_en_publicerad ON planforutsattningar (budgetar) WHERE status = 'publicerad';
CREATE UNIQUE INDEX planforutsattningar_ett_oppet ON planforutsattningar (budgetar) WHERE status IN ('utkast', 'granskad');
