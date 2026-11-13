-- En schemalagd körning minns vilken planerad tidpunkt den gällde, så att samma tidpunkt
-- aldrig körs två gånger och en missad tidpunkt kan tas igen.
ALTER TABLE insamlingskorning ADD COLUMN planerad_tid timestamptz;
