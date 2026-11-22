-- Rubriken hämtad ur ärendelistan (#88).
--
-- När tolkningen inte hittar en paragrafs rubrik men protokollets ärendelista eller
-- innehållsförteckning anger den, tas rubriken därifrån. Läsaren ser att den är hämtad ur ärendelistan.
ALTER TABLE behandling ADD COLUMN rubrik_ur_arendelistan boolean NOT NULL DEFAULT false;
