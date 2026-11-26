-- Granskade protokoll (#176).
--
-- En redaktör eller utgivare jämför tolkningen med protokollet och markerar hela protokollet som granskat.
-- En person räcker, eftersom tolkningen är plattformens arbete och inte en människas (ADR-0002).
--
-- Varje granskning är en rad, och raderna är loggen: vem som granskade och när, och hur granskningen
-- upphörde. En granskning gäller tills någon tar tillbaka den med en motivering, eller tills en omtolkning
-- ändrar någon uppgift. Det avgörs med fingeravtrycket av tolkningen från granskningstillfället
-- (protokollgranskning.py).

CREATE TABLE protokollgranskning (
    id              bigserial PRIMARY KEY,
    sammantrade_id  bigint NOT NULL REFERENCES sammantrade(id) ON DELETE CASCADE,
    granskad_av     text NOT NULL,
    granskad        timestamptz NOT NULL DEFAULT now(),
    fingeravtryck   text NOT NULL,
    status          text NOT NULL DEFAULT 'gallande' CHECK (status IN ('gallande', 'andrad', 'aterkallad')),
    -- andrad: en omtolkning ändrade någon uppgift.
    andrad          timestamptz,
    -- aterkallad: en redaktör eller utgivare tog tillbaka granskningen.
    aterkallad_av   text,
    aterkallad      timestamptz,
    aterkallelse    text,
    CHECK ((status = 'andrad') = (andrad IS NOT NULL)),
    CHECK ((status = 'aterkallad') = (aterkallad IS NOT NULL AND aterkallad_av IS NOT NULL AND aterkallelse IS NOT NULL))
);

CREATE INDEX ON protokollgranskning (sammantrade_id);
CREATE UNIQUE INDEX protokollgranskning_en_gallande ON protokollgranskning (sammantrade_id) WHERE status = 'gallande';
