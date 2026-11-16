-- Motioner och medborgarförslag (#45). Motionärerna enligt protokollets bakgrund till en motion,
-- som [{"namn": "Johan Wester", "parti": "C"}]. Namnet är null när protokollet bara anger partiet.
ALTER TABLE behandling ADD COLUMN motionarer jsonb NOT NULL DEFAULT '[]';
