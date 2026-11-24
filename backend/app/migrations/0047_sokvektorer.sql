-- Vektorsökning (#69): vilken text och vilken modell en sökenhets vektorer räknades för.
--
-- Vektorerna ligger i tabellen `sokstycke`, som kräver tillägget pgvector. Den skapas därför inte här
-- utan av `app.sokvektorer.forbered` när backend startar och tillägget finns i databasen. Utan
-- pgvector fungerar sökningen som i del 1, med enbart fulltext.
--
-- En enhet väntar på vektorer när `vektor_sha256` skiljer sig från `sha256` (texten har ändrats) eller
-- `vektor_modell` från modellen som används (modellbyte, ADR-0008).

ALTER TABLE sokenhet
    ADD COLUMN vektor_sha256 text,
    ADD COLUMN vektor_modell text;
