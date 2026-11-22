-- Sammanträdestider ur protokollens beslut när webbsidan saknar plan för året (#99).
--
-- Planens källa: 'webbsidan' (organets tabell) eller 'beslut' (organets beslut i ett protokoll, t.ex.
-- KF 2026-09-28 § 130 "Sammanträdestider 2027"). När tabellen publiceras tar den över samma rad.
ALTER TABLE sammantrade ADD COLUMN plan_kalla text CHECK (plan_kalla IN ('webbsidan', 'beslut'));
ALTER TABLE sammantrade ADD COLUMN plan_beslut_sammantrade_id bigint REFERENCES sammantrade(id) ON DELETE SET NULL;
ALTER TABLE sammantrade ADD COLUMN plan_beslut_paragraf integer;
UPDATE sammantrade SET plan_kalla = 'webbsidan' WHERE plan_nyckel IS NOT NULL;
ALTER TABLE sammantrade ADD CONSTRAINT sammantrade_plan_kalla CHECK ((plan_nyckel IS NULL) = (plan_kalla IS NULL));

ALTER TABLE planversion ADD COLUMN kalla text NOT NULL DEFAULT 'webbsidan' CHECK (kalla IN ('webbsidan', 'beslut'));
ALTER TABLE planversion ADD COLUMN beslut_sammantrade_id bigint REFERENCES sammantrade(id) ON DELETE SET NULL;
ALTER TABLE planversion ADD COLUMN beslut_paragraf integer;
