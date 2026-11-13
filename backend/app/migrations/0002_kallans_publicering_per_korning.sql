-- Senaste publicerade uppgift enligt källan, så som den såg ut vid varje kontroll.
ALTER TABLE kallkorning ADD COLUMN kallans_senaste_publicering date;
