-- Behandlingstypen (beslut, motion, informationsärende …) kan rättas av redaktionen (#44).
-- Typen räknas fram ur rubrik och beslut när behandlingen läses och lagras inte.

ALTER TABLE rattelse DROP CONSTRAINT rattelse_check;
ALTER TABLE rattelse ADD CONSTRAINT rattelse_check CHECK (
    (objekt = 'behandling' AND paragraf IS NOT NULL AND falt IN ('rubrik', 'beslut', 'diarienummer', 'typ'))
    OR (objekt = 'rost' AND paragraf IS NOT NULL AND votering IS NOT NULL AND namn <> '' AND falt IN ('rost', 'parti'))
    OR (objekt = 'narvaro' AND namn <> '' AND falt = 'parti')
);
