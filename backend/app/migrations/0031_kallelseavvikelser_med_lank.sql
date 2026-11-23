-- Avvikelser mot kallelsen med länk till kallelsen (#121).
--
-- Kallelsens avvikelser sparas som objekt {text, lank} i stället för strängar. De befintliga strängarna
-- slås in här med lank = null. Texten och länken får de när kompletteringen räknas om
-- (`kallelsepunkter.komplettera`), nästa gång ett protokoll eller en kallelse läses.
UPDATE sammantrade s
SET kallelse_avvikelser = (
    SELECT jsonb_agg(CASE WHEN jsonb_typeof(a) = 'string' THEN jsonb_build_object('text', a, 'lank', NULL) ELSE a END
                     ORDER BY i)
    FROM jsonb_array_elements(s.kallelse_avvikelser) WITH ORDINALITY AS x(a, i)
)
WHERE s.kallelse_avvikelser <> '[]';
