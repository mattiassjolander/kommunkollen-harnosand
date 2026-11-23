-- Ändra publicerade planförutsättningar och budgetförslag i efterhand (#76, del 2).
--
-- En ny version skapas från en publicerad eller återkallad version, som ett utkast med samma uppgifter, och
-- pekar på den den ersätter. `andring` är motiveringen till ändringen. Den nya versionen går granskad →
-- publicerad som vanligt, och läsaren ser den märkt "Ändrad efter publicering" och kan öppna den förra.
-- En ny inläsning av en ändrad fil skapar också en ny version av den publicerade eller återkallade.
ALTER TABLE planforutsattningar ADD COLUMN ersatter_id bigint REFERENCES planforutsattningar(id) ON DELETE SET NULL;
ALTER TABLE planforutsattningar ADD COLUMN andring text;
ALTER TABLE budgetforslag ADD COLUMN ersatter_id bigint REFERENCES budgetforslag(id) ON DELETE SET NULL;
ALTER TABLE budgetforslag ADD COLUMN andring text;
