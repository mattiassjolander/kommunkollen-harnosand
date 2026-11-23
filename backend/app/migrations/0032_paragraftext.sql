-- Paragrafens text utan beslut (#124).
--
-- En paragraf utan underrubriker och beslut, t.ex. "Allmänhetens frågestund" med texten "Inga frågor har
-- inkommit till dagens frågestund.", fick tidigare hela sin text i rubriken. När rubriken avgränsas med
-- protokollets ärendelista sparas resten här och visas på behandlingen.
ALTER TABLE behandling ADD COLUMN paragraftext text;
