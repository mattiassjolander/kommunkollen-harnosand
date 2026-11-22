-- Återkalla publicerade planförutsättningar och budgetförslag (#76, del 1).
--
-- En utgivare tar bort en publicerad uppgift från visning, direkt och med motivering, när den innehåller
-- fel. Den återkallade versionen bevaras med vem, när och varför. Läsaren ser en notis i stället, tills en
-- rättad version har publicerats i det vanliga flödet. Den förra publicerade versionen kommer inte tillbaka.
ALTER TABLE planforutsattningar ADD COLUMN aterkallad_av text;
ALTER TABLE planforutsattningar ADD COLUMN aterkallad timestamptz;
ALTER TABLE planforutsattningar ADD COLUMN aterkallelse text;
ALTER TABLE planforutsattningar DROP CONSTRAINT planforutsattningar_status_check;
ALTER TABLE planforutsattningar ADD CONSTRAINT planforutsattningar_status_check
    CHECK (status IN ('utkast', 'granskad', 'publicerad', 'ersatt', 'aterkallad'));
ALTER TABLE planforutsattningar ADD CONSTRAINT planforutsattningar_aterkallad
    CHECK ((status = 'aterkallad') = (aterkallad IS NOT NULL));

ALTER TABLE budgetforslag ADD COLUMN aterkallad_av text;
ALTER TABLE budgetforslag ADD COLUMN aterkallad timestamptz;
ALTER TABLE budgetforslag ADD COLUMN aterkallelse text;
ALTER TABLE budgetforslag DROP CONSTRAINT budgetforslag_status_check;
ALTER TABLE budgetforslag ADD CONSTRAINT budgetforslag_status_check
    CHECK (status IN ('utkast', 'granskad', 'publicerad', 'ersatt', 'aterkallad'));
ALTER TABLE budgetforslag ADD CONSTRAINT budgetforslag_aterkallad
    CHECK ((status = 'aterkallad') = (aterkallad IS NOT NULL));
