"""Behandlingstyp ur rubrik och beslut. Exemplen är tagna ur de olika organens protokoll 2022–2026."""

import pytest

from app.behandlingstyper import klassa


@pytest.mark.parametrize(
    ("rubrik", "beslut", "typ"),
    [
        # Motioner, också när de bereds i en nämnd eller besvaras.
        ("Motion - Fixa soptunnorna", "Kommunfullmäktige beslutar\natt överlämna motionen till kommunstyrelsen för beredning.",
         "motion"),
        ("Motion - Skolfrukost", "Skolnämnden föreslår kommunstyrelsen att föreslå kommunfullmäktige besluta\natt avslå motionen.",
         "motion"),
        ("Svar på motion - Inför elektronisk körjournal", "Kommunstyrelsen föreslår kommunfullmäktige besluta\natt anse motionen besvarad.",
         "motion"),
        ("Svar på remiss angående motion- Inför elektronisk körjournal", "Samhällsnämnden beslutar\natt anta remissyttrandet",
         "motion"),
        # Medborgarförslag heter e-förslag i Härnösand.
        ("E-förslag - Grillplats vid landsarkivet", "Samhällsnämnden beslutar\natt avslå e-förslaget", "medborgarforslag"),
        ("E-förslag 111 - Möjligheter i Häggdånger", "Kommunstyrelsen beslutar\natt bifalla e-förslaget", "medborgarforslag"),
        ("Interpellation - Agera för företagsklimatet", "Kommunfullmäktige beslutar\natt interpellationen får ställas",
         "interpellation"),
        ("Korta frågor - korta svar 2024", "Kommunfullmäktige beslutar\natt anse frågorna besvarade.", "interpellation"),
        ("Allmänhetens frågestund i kommunfullmäktige 2026", "Kommunfullmäktige beslutar\natt anse frågorna besvarade.",
         "interpellation"),
        # Informationsärenden: på rubriken, eller på ett beslut som bara lägger något till handlingarna.
        ("Informationsärenden 2023", "Socialnämnden beslutar\natt tacka för informationen och lägga den till handlingarna.",
         "information"),
        ("Informationsärenden", "", "information"),
        ("Anmälan av delegationsbeslut 2025", "Kommunstyrelsen beslutar\natt godkänna redovisningen av delegationsbeslut.",
         "information"),
        ("Ärenden för kännedom", "Samhällsnämnden beslutar\natt lägga ärenden för kännedom till handlingarna.", "information"),
        ("Delgivningar", "Skolnämnden beslutar\natt lägga delgivningar till handlingarna.", "information"),
        ("Förvaltningschef rapporterar", "Samhällsnämnden beslutar\natt lägga informationen till handlingarna.", "information"),
        ("Budgetuppföljning februari", "Samhällsnämnden beslutar\natt lägga informationen till handlingarna.", "information"),
        # Formalia.
        ("Val av justerare", "Kommunstyrelsen beslutar\natt välja Eva-Clara Viklund (M) till justerare.", "formalia"),
        ("Fastställande av föredragningslista 2024", "Kommunstyrelsen beslutar\natt fastställa föredragningslistan.", "formalia"),
        ("Eventuellt tillkommande ärende Inget tillkommande ärende. ______", "", "formalia"),
        ("Tillkommande motioner, interpellationer och frågor", "Kommunfullmäktige beslutar\natt överlämna motionen", "formalia"),
        # Förslag till ett annat organ, och beslut.
        ("Partistöd 2026", "Kommunstyrelsen föreslår kommunfullmäktige besluta\natt partistöd utbetalas", "forslag"),
        ("Hyresavtal Härnösandshus gällande simhallen", "Samhällsnämnden föreslår kommunstyrelsen\natt uppdra till kommundirektören",
         "forslag"),
        ("Verksamhetsberättelse med årsbokslut 2025", "Skolförvaltningen föreslår skolnämnden besluta\natt godkänna", "beslut"),
        ("Avsägelser 2026", "Kommunfullmäktige beslutar\natt godkänna avsägelse från Karin Lundqvist (V)", "beslut"),
        ("Årsredovisning 2021 Härnösands kommun", "Kommunfullmäktige besluta\natt godkänna årsredovisning", "beslut"),
        ("Grundbelopp 2023", "Skolnämnden beslutar\natt för budgetår 2023 fastställa ett grundbelopp", "beslut"),
        # Utan regel och utan beslutstext: ingen typ.
        ("Tidsbegränsat bygglov - Paviljong på fastighet Ön 2:52", "", None),
        ("Nya uppdrag", "Inga nya uppdrag är föreslagna från presidiet.", None),
    ],
)
def test_behandlingstyp(rubrik, beslut, typ):
    assert klassa(rubrik, beslut) == typ
