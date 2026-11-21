-- Motionärer kan rättas (#78). Rättelsen hör till en behandling och anger hela listan med motionärer:
-- [{person_id, namn, parti}], där en partigrupp har person_id och namn null.

ALTER TABLE rattelse DROP CONSTRAINT rattelse_check;
ALTER TABLE rattelse ADD CONSTRAINT rattelse_check CHECK (
    (objekt = 'behandling' AND paragraf IS NOT NULL AND falt IN ('rubrik', 'beslut', 'diarienummer', 'typ', 'motionarer'))
    OR (objekt = 'rost' AND paragraf IS NOT NULL AND votering IS NOT NULL AND namn <> '' AND falt IN ('rost', 'parti'))
    OR (objekt = 'narvaro' AND namn <> '' AND falt = 'parti')
);
