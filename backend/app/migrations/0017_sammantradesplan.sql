-- Planerade sammanträden enligt organens sammanträdesplaner (#68).
--
-- Ett planerat sammanträde och protokollet för det är samma sammanträde. Ett planerat sammanträde
-- har inget protokoll än, så dokument_id och tolkningen kan saknas. Planens uppgifter ligger i
-- plan_*-kolumnerna och finns kvar när protokollet kopplas till sammanträdet.
ALTER TABLE sammantrade ALTER COLUMN dokument_id DROP NOT NULL;
ALTER TABLE sammantrade ALTER COLUMN tolkning DROP NOT NULL;
ALTER TABLE sammantrade ALTER COLUMN tolkad DROP NOT NULL;
ALTER TABLE sammantrade ADD CONSTRAINT sammantrade_protokoll_eller_plan
    CHECK ((dokument_id IS NOT NULL AND tolkning IS NOT NULL AND tolkad IS NOT NULL) OR dokument_id IS NULL);

-- Radens nyckel i organets plan: datumet, eller "ÅÅÅÅ-MM" för en månad som bara anges som inställd.
ALTER TABLE sammantrade ADD COLUMN plan_nyckel text;
ALTER TABLE sammantrade ADD COLUMN plan_datum date;
ALTER TABLE sammantrade ADD COLUMN plan_starttid text;
ALTER TABLE sammantrade ADD COLUMN plan_status text CHECK (plan_status IN ('planerat', 'installt', 'borttaget'));
ALTER TABLE sammantrade ADD COLUMN plan_anmarkning text;
ALTER TABLE sammantrade ADD COLUMN plan_url text;
ALTER TABLE sammantrade ADD COLUMN plan_version integer;
ALTER TABLE sammantrade ADD CONSTRAINT sammantrade_plan_komplett
    CHECK ((plan_nyckel IS NULL) = (plan_status IS NULL) AND (plan_nyckel IS NULL) = (plan_version IS NULL));
CREATE UNIQUE INDEX sammantrade_plan_nyckel ON sammantrade (organ, plan_nyckel) WHERE plan_nyckel IS NOT NULL;

-- Planens versioner, append-only: varje ändring på sidan blir en reviderad uppgift.
CREATE TABLE planversion (
    sammantrade_id  bigint NOT NULL REFERENCES sammantrade(id) ON DELETE CASCADE,
    version         integer NOT NULL,
    datum           date,
    starttid        text,
    status          text NOT NULL CHECK (status IN ('planerat', 'installt', 'borttaget')),
    anmarkning      text,
    kalltext        text NOT NULL,
    hamtad          timestamptz NOT NULL,
    korning_id      bigint REFERENCES insamlingskorning(id),
    PRIMARY KEY (sammantrade_id, version)
);
