-- Processdiagram med aktörer i banor (#158).
--
-- Varje steg får en aktör: ett kort namn som bestämmer stegets bana i processdiagrammet (GLOSSARY.md). Fältet `vem`
-- står kvar. En övergång säger att ett steg följs av ett annat i samma process, eventuellt under ett villkor. Ett steg
-- med flera övergångar är ett vägval, och varje övergång har då ett villkor. Ett steg utan övergång avslutar processen.
--
-- Stegen som lästes in före #158 saknar aktör. Diagrammet visas bara när alla steg i processen har aktör, och skillen
-- läser in stegen igen.

ALTER TABLE process_steg ADD COLUMN aktor text;

CREATE TABLE process_overgang (
    fran_steg bigint NOT NULL REFERENCES process_steg(id) ON DELETE CASCADE,
    till_steg bigint NOT NULL REFERENCES process_steg(id) ON DELETE CASCADE,
    villkor   text,
    PRIMARY KEY (fran_steg, till_steg),
    CHECK (fran_steg <> till_steg)
);

CREATE INDEX ON process_overgang (till_steg);
