-- Förslag i en batch (#100, del 2). Perioder som redaktören bekräftar tillsammans får samma batch, så att en
-- utgivare kan granska och publicera dem på en gång. En period som registreras för sig har ingen batch.
CREATE SEQUENCE partitillhorighet_batch_seq;
ALTER TABLE partitillhorighet ADD COLUMN batch bigint;
CREATE INDEX ON partitillhorighet (batch) WHERE batch IS NOT NULL;
