-- Märkningar i sökindexet (#162): votering, reservation, oenighet m.fl. för behandlingar och ärenden.
--
-- Märkningarna räknas regelbundet ur protokollen med publicerade rättelser (app.markningar) och sparas
-- med sökenheten, [{"id": "votering", "text": "Votering 26–24"}, …], så att sökningen kan filtrera på dem.
-- Befintliga enheter får märkningarna när indexet uppdateras nästa gång (python -m app.sokindex).

ALTER TABLE sokenhet ADD COLUMN markningar jsonb NOT NULL DEFAULT '[]';

CREATE INDEX sokenhet_markningar ON sokenhet USING gin (markningar jsonb_path_ops);
