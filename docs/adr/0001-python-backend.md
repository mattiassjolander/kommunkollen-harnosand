# Python (FastAPI) och Postgres i backend

Backend, alltså både insamling, dokumentextraktion och API, skrivs i Python med FastAPI mot Postgres. Det avviker från Avvikelser-projektet (Spring Boot). Det tyngsta och mest riskfyllda arbetet är att tolka PDF:er (protokoll, voteringsbilagor, årsredovisningar) och att anropa statistik-API:er, och där är Pythons ekosystem klart starkare. Ett enda backend-språk räcker för ett soloprojekt, i stället för en Python-insamlare bredvid ett Java-API.

## Considered Options

- Spring Boot för API + Python för insamling: återanvänder kunskap från Avvikelser, men ger två språk, två byggen och delade datamodeller.
