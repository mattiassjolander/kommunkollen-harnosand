-- Namnen i protokollen (#165).
--
-- "Tom plats för Namn" är ingen person utan en tom stol. Personen räknas som frånvarande, och
-- sammanträdets sida visar att platsen var tom.
ALTER TABLE narvaro ADD COLUMN tom_plats boolean NOT NULL DEFAULT false;

-- Namnvarianter som bara skiljer sig i bindestreck eller mellanslag slås ihop automatiskt. Felaktiga namn
-- som inte längre förekommer i någon närvarolista tas bort ur registret. Händelserna loggas med namnet, så
-- att historiken finns kvar när namnet är borttaget.
ALTER TABLE ledamot_handelse ADD COLUMN namn text;
UPDATE ledamot_handelse h SET namn = l.namn FROM ledamot l WHERE l.id = h.ledamot_id;
ALTER TABLE ledamot_handelse ADD COLUMN automatisk boolean NOT NULL DEFAULT false;
ALTER TABLE ledamot_handelse ALTER COLUMN ledamot_id DROP NOT NULL;
ALTER TABLE ledamot_handelse DROP CONSTRAINT ledamot_handelse_typ_check;
ALTER TABLE ledamot_handelse ADD CONSTRAINT ledamot_handelse_typ_check
    CHECK (typ IN ('sammanslagning', 'uppdelning', 'borttagning'));
ALTER TABLE ledamot_handelse DROP CONSTRAINT ledamot_handelse_ledamot_id_fkey;
ALTER TABLE ledamot_handelse ADD CONSTRAINT ledamot_handelse_ledamot_id_fkey
    FOREIGN KEY (ledamot_id) REFERENCES ledamot(id) ON DELETE SET NULL;
ALTER TABLE ledamot_handelse DROP CONSTRAINT ledamot_handelse_huvud_id_fkey;
ALTER TABLE ledamot_handelse ADD CONSTRAINT ledamot_handelse_huvud_id_fkey
    FOREIGN KEY (huvud_id) REFERENCES ledamot(id) ON DELETE SET NULL;
ALTER TABLE ledamot_handelse DROP CONSTRAINT ledamot_handelse_tidigare_huvud_id_fkey;
ALTER TABLE ledamot_handelse ADD CONSTRAINT ledamot_handelse_tidigare_huvud_id_fkey
    FOREIGN KEY (tidigare_huvud_id) REFERENCES ledamot(id) ON DELETE SET NULL;

-- Förslag på namnvarianter med ett mellannamn eller en annan stavning. En redaktör bekräftar (namnen slås
-- ihop) eller avvisar (förslaget kommer inte tillbaka). Plattformen slår aldrig ihop dem själv (ADR-0002).
CREATE TABLE namnforslag (
    id          bigserial PRIMARY KEY,
    ledamot_id  bigint NOT NULL REFERENCES ledamot(id) ON DELETE CASCADE,
    annat_id    bigint NOT NULL REFERENCES ledamot(id) ON DELETE CASCADE,
    skal        text NOT NULL,
    status      text NOT NULL CHECK (status IN ('forslag', 'bekraftad', 'avvisad')),
    skapad      timestamptz NOT NULL DEFAULT now(),
    beslutad_av text,
    beslutad    timestamptz,
    CHECK (ledamot_id < annat_id),
    UNIQUE (ledamot_id, annat_id)
);
