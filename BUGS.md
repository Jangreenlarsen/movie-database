# Bugs

Registrér bugs så snart de opdages (jf. CLAUDE.md regel 3). Opdatér status og tilføj løsning når fikset.

| # | Beskrivelse | Status | Løsning | Version fikset |
|---|-------------|--------|---------|-----------------|
| 1 | Kun **én** film uden stregkode kunne oprettes ad gangen. `movie_service.create_movie` satte altid `"barcode": payload.barcode` i dokumentet (dvs. `null` når ikke angivet). Den sparse unique-index på `barcode` ekskluderer kun dokumenter hvor feltet helt *mangler* — ikke dokumenter hvor det eksplicit er `null`. To film uden stregkode kolliderede derfor på indexet. Opdaget live mod ægte MongoDB (mongomock i testsuiten fangede det ikke — kendt unøjagtighed i dens sparse-index-håndtering). | fixed | `create_movie` udelader nu `barcode`-nøglen helt fra dokumentet når `payload.barcode` er `None`, i stedet for at sætte den til `null`. Eksisterende data migreret (`$unset` på dokumenter med `barcode: null`). Regressionstests tilføjet i `test_movies.py` (`test_multiple_movies_without_barcode_are_allowed`, `test_movie_without_barcode_omits_field_entirely`). | 0.4.0 |
