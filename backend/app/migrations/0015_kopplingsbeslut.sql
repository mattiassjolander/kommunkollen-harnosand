-- Historik över redaktörens beslut om kopplingar (#77).
--
-- Varje beslut sparas och skrivs aldrig över: bekräftad, avvisad eller tillbaka till förslag, med
-- redaktör, tid och motivering. Kopplingens status och redaktör är det senaste beslutet. En ändring av
-- ett tidigare beslut kräver motivering. De beslut som redan finns blir historikens första post.

CREATE TABLE kopplingsbeslut (
    id          bigserial PRIMARY KEY,
    koppling_id bigint NOT NULL REFERENCES koppling(id) ON DELETE CASCADE,
    status      text NOT NULL CHECK (status IN ('forslag', 'bekraftad', 'avvisad')),
    redaktor    text NOT NULL,
    tid         timestamptz NOT NULL,
    motivering  text
);

CREATE INDEX kopplingsbeslut_koppling ON kopplingsbeslut (koppling_id, tid);

INSERT INTO kopplingsbeslut (koppling_id, status, redaktor, tid)
SELECT id, status, redaktor, beslutad FROM koppling
WHERE status IN ('bekraftad', 'avvisad') AND redaktor IS NOT NULL AND beslutad IS NOT NULL;
