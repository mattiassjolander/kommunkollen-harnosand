-- Kopplingsregeln motionstitel (#108): ett svar på en motion kopplas till kommunfullmäktiges beslut att
-- väcka motionen när titlarna är lika. Underlaget är den normaliserade titeln.
ALTER TABLE koppling DROP CONSTRAINT koppling_grund_check;
ALTER TABLE koppling ADD CONSTRAINT koppling_grund_check
    CHECK (grund IN ('diarienummer', 'hanvisning', 'motionstitel'));
