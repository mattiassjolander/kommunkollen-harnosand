-- Protokoll som bara innehåller bilder läses med OCR (#52). Det som tolkats ur OCR-text märks.
ALTER TABLE sammantrade ADD COLUMN ocr boolean NOT NULL DEFAULT false;
