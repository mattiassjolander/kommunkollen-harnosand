-- Protokoll med flera sittningar samma dag (#85).
--
-- Ett protokoll kan ha flera försättsblad, ett per sittning, med egen plats och tid, egna beslutande
-- och egna paragrafer. Kommunstyrelsens protokoll 2022-01-18 har hela styrelsen för §§ 1–14 och
-- presidiet, som beslutar på delegation, för § 15. Sammanträdets plats och tid är den första
-- sittningens. Närvaron per sittning står i narvaro.paragrafer. Raderna finns bara när protokollet
-- har fler än en sittning, och tolkas om med protokollet.
CREATE TABLE sittning (
    id              bigserial PRIMARY KEY,
    sammantrade_id  bigint NOT NULL REFERENCES sammantrade(id) ON DELETE CASCADE,
    ordning         integer NOT NULL,
    plats           text,
    starttid        text,
    sluttid         text,
    paragrafer      integer[] NOT NULL,
    -- Den som fattade sittningens beslut på delegation enligt beslutsformeln, t.ex. 'kommunstyrelsens presidium'.
    delegation      text
);

CREATE INDEX ON sittning (sammantrade_id);
