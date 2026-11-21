-- SKR:s skatteunderlagsprognoser (#61).
--
-- Varje cirkulär är en egen skatteunderlagsprognos. Publicerar SKR samma cirkulär igen med andra
-- värden blir det en ny version, och den tidigare finns kvar. Beloppen är i tkr, per år.

CREATE TABLE skatteunderlagsprognos (
    id              bigserial PRIMARY KEY,
    cirkular        text NOT NULL,                   -- t.ex. '26:28'
    kommun          text NOT NULL,                   -- kommunkod, '2280'
    version         integer NOT NULL,
    publicerad      date NOT NULL,                   -- cell J1 i Prognosunderlag
    url             text NOT NULL,                   -- filen på SKR:s sida, källhänvisningen
    filnamn         text NOT NULL,
    sha256          text NOT NULL,
    skattesats      numeric NOT NULL,                -- skattesatsen prognosen räknar med
    ar              jsonb NOT NULL,                  -- [2026, …, 2033]
    rader           jsonb NOT NULL,                  -- [{id, etikett, tkr: {"2026": …}}]
    invanare        jsonb NOT NULL,                  -- {"2026": 24333, …}, riksprognosen
    hamtad          timestamptz NOT NULL,
    korning_id      bigint NOT NULL REFERENCES insamlingskorning(id),
    UNIQUE (cirkular, kommun, version)
);
