-- Rankningar (#66): externa aktörers återkommande jämförelser av Sveriges kommuner, t.ex. Svenskt Näringslivs
-- lokala företagsklimat och Aktuell Hållbarhets miljöbästa kommun.
--
-- Uppgifterna är avsändarens officiella siffror och publiceras direkt, utan granskningsflödet, med källhänvisning.
-- De sparas för Härnösand och grannkommunerna (kravspec avsnitt 18). Placeringar och delmått är append-only som
-- observationerna: ett nytt värde för ett år som redan finns blir en ny version (reviderad uppgift), och de
-- tidigare versionerna finns kvar.

CREATE TABLE rankning (
    id            text PRIMARY KEY,
    titel         text NOT NULL,
    avsandare     text NOT NULL,
    avsandartyp   text NOT NULL,  -- vilken sorts organisation avsändaren är
    beskrivning   text NOT NULL,  -- vad avsändaren mäter, utan värdering
    url           text NOT NULL,
    metod_url     text NOT NULL,
    villkor       text NOT NULL,  -- källans användarvillkor, så som plattformen följer dem
    datakalla_id  text NOT NULL REFERENCES datakalla(id)
);

-- Ett år då rankningen har ändrat sin metod så att placeringarna före och efter inte går att jämföra.
-- Registreras av en redaktör. Linjen i diagrammet bryts mellan året före och metodbytesåret.
CREATE TABLE rankning_metodbyte (
    rankning_id   text NOT NULL REFERENCES rankning(id),
    ar            integer NOT NULL,
    beskrivning   text NOT NULL,
    registrerad_av text NOT NULL,
    registrerad   timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (rankning_id, ar)
);

CREATE TABLE rankning_placering (
    id            bigserial PRIMARY KEY,
    rankning_id   text NOT NULL REFERENCES rankning(id),
    kommun        text NOT NULL,
    ar            integer NOT NULL,
    placering     integer NOT NULL,
    antal         integer,         -- antal rankade kommuner, om källan anger det
    poang         numeric,         -- total poäng eller totalt värde, om rankningen har det
    max_poang     numeric,
    kalla_url     text NOT NULL,
    hamtad        timestamptz NOT NULL,
    version       integer NOT NULL,
    korning_id    bigint REFERENCES insamlingskorning(id),
    UNIQUE (rankning_id, kommun, ar, version)
);

CREATE TABLE rankning_delmatt (
    id            bigserial PRIMARY KEY,
    rankning_id   text NOT NULL REFERENCES rankning(id),
    kommun        text NOT NULL,
    ar            integer NOT NULL,
    delmatt       text NOT NULL,   -- källans beteckning, t.ex. faktorns namn eller indikatorns nummer
    namn          text NOT NULL,
    grupp         text NOT NULL,   -- t.ex. "Enkät", "Statistik", "Extern data"
    enhet         text NOT NULL,
    varde         numeric,
    svar          text,            -- svaret på en enkätfråga, när källan anger det, t.ex. "Ja"
    riksvarde     numeric,
    placering     integer,
    kalla_url     text NOT NULL,
    hamtad        timestamptz NOT NULL,
    version       integer NOT NULL,
    korning_id    bigint REFERENCES insamlingskorning(id),
    UNIQUE (rankning_id, kommun, ar, delmatt, version)
);

CREATE INDEX ON rankning_delmatt (rankning_id, kommun, ar);
