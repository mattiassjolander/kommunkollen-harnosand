-- Sammansättning: kön och ålder bland kandidater, valda och tjänstgörande (#65).
--
-- Valmyndighetens öppna data om valen till kommunfullmäktige i Härnösand. En person i valet identifieras med
-- valår och kandidatnummer, som är detsamma i kandidaturerna, bland de valda och bland ersättarna. Kön och ålder
-- är källans uppgifter enligt folkbokföringen. Valmyndigheten gallrar kandidaternas personuppgifter i efterhand,
-- så ett värde som redan är sparat skrivs aldrig över av "Gallrad uppgift".

-- En fil som hämtats från Valmyndigheten, med källans tidsstämpel och när plattformen hämtade den.
CREATE TABLE valfil (
    valar        integer NOT NULL,
    fil          text NOT NULL,              -- 'kandidaturer', 'ledamoter_med_historik', 'ledamoter_och_ersattare', 'rostberattigade'
    url          text NOT NULL,
    stampel      text,                       -- källans tidsstämpel, t.ex. "Valmyndigheten 2026-10-30 15:51:49"
    hamtad       timestamptz NOT NULL,
    PRIMARY KEY (valar, fil)
);

-- En kandidat på ett partis lista till kommunfullmäktige.
CREATE TABLE valkandidat (
    valar                integer NOT NULL,
    kandidatnummer       integer NOT NULL,
    parti                text NOT NULL,      -- plattformens förkortning (NorrP blir NP)
    listnummer           text,
    ordning              integer,            -- placering på listan
    namn                 text,
    alder                integer,            -- ålder på valdagen
    kon                  text CHECK (kon IN ('K', 'M')),
    folkbokforingskommun text,
    giltig               boolean NOT NULL DEFAULT true,
    gallrad              timestamptz,        -- när källan först angav "Gallrad uppgift"
    hamtad               timestamptz NOT NULL,
    PRIMARY KEY (valar, kandidatnummer)
);

-- Ett mandat i fullmäktige: den invalde ledamoten och efterträdarna under mandatperioden.
CREATE TABLE valledamot (
    valar          integer NOT NULL,
    kandidatnummer integer NOT NULL,
    parti          text NOT NULL,
    mandat         integer NOT NULL,         -- invalsordning inom partiet
    namn           text NOT NULL,
    invald         date,                     -- NULL: från mandatperiodens start
    avgang         date,
    personvald     boolean NOT NULL DEFAULT false,
    alder          integer,
    kon            text CHECK (kon IN ('K', 'M')),
    hamtad         timestamptz NOT NULL,
    PRIMARY KEY (valar, kandidatnummer)
);

-- En ersättare i en ersättargrupp. Samma ersättare står ofta i flera grupper.
CREATE TABLE valersattare (
    valar                   integer NOT NULL,
    parti                   text NOT NULL,
    ledamot_kandidatnummer  integer NOT NULL,
    ersattargrupp           integer,
    ersattarordning         integer NOT NULL,
    kandidatnummer          integer NOT NULL,
    namn                    text NOT NULL,
    hamtad                  timestamptz NOT NULL,
    PRIMARY KEY (valar, ledamot_kandidatnummer, ersattarordning)
);

-- Reviderade uppgifter: källan har ändrat ett värde, till exempel en ny efterträdare eller ett avgångsdatum.
-- Det tidigare värdet finns kvar här.
CREATE TABLE valandring (
    id          bigserial PRIMARY KEY,
    tabell      text NOT NULL,
    nyckel      text NOT NULL,              -- t.ex. "2026/24625"
    falt        text NOT NULL,              -- fältet, eller 'rad' när en rad tillkommit eller försvunnit
    tidigare    text,
    nytt        text,
    korning_id  bigint REFERENCES insamlingskorning(id),
    hamtad      timestamptz NOT NULL
);

-- De röstberättigade i Härnösand på valdagen, per kön och åldersgrupp (två separata indelningar).
CREATE TABLE rostberattigade (
    valar     integer PRIMARY KEY,
    kvinnor   integer NOT NULL,
    man       integer NOT NULL,
    a18_29    integer NOT NULL,
    a30_49    integer NOT NULL,
    a50_64    integer NOT NULL,
    a65       integer NOT NULL,
    totalt    integer NOT NULL,
    hamtad    timestamptz NOT NULL
);

-- Kopplingen mellan en person i valet och en person i ledamotsregistret. Säkra matchningar kopplas automatiskt,
-- osäkra blir förslag som en redaktör bekräftar eller avvisar.
CREATE TABLE valkoppling (
    id             bigserial PRIMARY KEY,
    valar          integer NOT NULL,
    kandidatnummer integer NOT NULL,
    ledamot_id     bigint NOT NULL REFERENCES ledamot(id),
    status         text NOT NULL CHECK (status IN ('automatisk', 'forslag', 'bekraftad', 'avvisad')),
    skal           text NOT NULL,
    skapad         timestamptz NOT NULL DEFAULT now(),
    beslutad_av    text,
    beslutad       timestamptz,
    UNIQUE (valar, kandidatnummer, ledamot_id)
);

-- Kön och födelseår som en redaktör anger med källa för en person som saknar uppgift hos Valmyndigheten.
-- Går genom granskningsflödet (ADR-0002): utkast, granskad, publicerad.
CREATE TABLE personuppgift (
    id            bigserial PRIMARY KEY,
    ledamot_id    bigint NOT NULL REFERENCES ledamot(id),
    kon           text CHECK (kon IN ('K', 'M')),
    fodelsear     integer CHECK (fodelsear BETWEEN 1900 AND 2100),
    kalla         text NOT NULL,             -- länk, eller dokument och sida
    status        text NOT NULL CHECK (status IN ('utkast', 'granskad', 'publicerad', 'aterkallad')),
    redaktor      text NOT NULL,
    skapad        timestamptz NOT NULL DEFAULT now(),
    granskad_av   text,
    granskad      timestamptz,
    publicerad_av text,
    publicerad    timestamptz,
    aterkallad_av text,
    aterkallad    timestamptz,
    aterkallelse  text,
    CHECK (kon IS NOT NULL OR fodelsear IS NOT NULL)
);
