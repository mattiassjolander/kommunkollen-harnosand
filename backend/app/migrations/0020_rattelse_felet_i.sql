-- Var felet finns som en rättelse rättar (#74): i protokollet (källan saknar eller anger fel uppgift)
-- eller i inläsningen (plattformen läste eller tolkade fel). Rättelser från före #74 har inget värde
-- ("Inte angivet") och ger ingen markering förrän det anges.
ALTER TABLE rattelse ADD COLUMN felet_i text CHECK (felet_i IN ('protokollet', 'inlasningen'));
CREATE INDEX ON rattelse (sammantrade_id) WHERE status = 'publicerad' AND felet_i = 'protokollet';
