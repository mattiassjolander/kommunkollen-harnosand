-- Ändra en granskad eller publicerad rättelse genom en ny version, och återkalla en publicerad (#74, del 3).
-- Den nya versionen pekar på den den ersätter. Den gamla bevaras som historik, med status ersatt när den nya
-- publiceras. En återkallad rättelse gäller inte längre, och tolkningen gäller igen.
ALTER TABLE rattelse ADD COLUMN ersatter_id bigint REFERENCES rattelse(id) ON DELETE SET NULL;
ALTER TABLE rattelse ADD COLUMN aterkallad_av text;
ALTER TABLE rattelse ADD COLUMN aterkallad timestamptz;
ALTER TABLE rattelse ADD COLUMN aterkallelse text;
ALTER TABLE rattelse DROP CONSTRAINT rattelse_status_check;
ALTER TABLE rattelse ADD CONSTRAINT rattelse_status_check
    CHECK (status IN ('utkast', 'granskad', 'publicerad', 'ersatt', 'aterkallad'));
ALTER TABLE rattelse ADD CONSTRAINT rattelse_aterkallad CHECK ((status = 'aterkallad') = (aterkallad IS NOT NULL));
