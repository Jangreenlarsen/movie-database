"""Fritekst-søgning delt af film- og TV-repositoriet (BUGS.md #48).

Søgningen brugte tidligere Mongos `$text` mod et index på titel+overview.
Det gjorde tre ting galt på én gang:

1. `cast`/`director`/`creators`/`genres` var aldrig med i indexet, så et
   skuespillernavn i søgefeltet fandt aldrig noget — stik imod både
   placeholderen i UI'et og CLAUDE.md regel 7.
2. `$text` matcher kun hele ord. I et søgefelt der søger for hvert tastetryk
   betyder det nul resultater indtil ordet er skrevet helt færdigt.
3. mongomock implementerer ikke `$text` (`NotImplementedError`), så
   søgningen var bogstavelig talt utestbar i projektets testsuite — og var
   derfor også helt utestet.

Et felt-eksplicit regex-match løser alle tre. Prisen er at et regex-scan er
langsommere end et text-index og ikke rangerer efter relevans; begge dele er
uproblematiske her, hvor biblioteket er en privat samling og resultaterne
alligevel vises i brugerens egen valgte sortering, ikke efter score.
"""

import re


# Feature #95 — et serienummer som brugeren ville skrive det: valgfrit
# serie-bogstav, valgfrie foranstillede nuller, og tallet. "M42", "m0042",
# "D7" og "42" er alle gyldige.
_SERIAL_TERM = re.compile(r"^([a-zA-Z]?)0*(\d+)$")


def _serial_clause(term: str, serial_prefixes: dict[str, str] | None) -> dict | None:
    """Mongo-filter for et søgeord der ligner et serienummer, eller None.

    Uden serie-bogstav matches nummeret i alle serier — man skal kunne slå
    "42" op uden at vide om det er en fysisk eller digital udgave. Med et
    bogstav afgrænses der til den serie bogstavet står for, så "M42" ikke
    også finder D42, som er en helt anden film.

    Et ukendt bogstav giver None frem for et filter der matcher ingenting:
    så falder ordet tilbage til den almindelige tekstsøgning, hvor "S1" i en
    titel stadig kan findes."""
    if not serial_prefixes:
        return None
    match = _SERIAL_TERM.match(term)
    if match is None:
        return None

    letter, digits = match.groups()
    number = int(digits)
    if not letter:
        return {"serial_number": number}

    media_type = serial_prefixes.get(letter.upper())
    if media_type is None:
        return None
    return {"serial_number": number, "media_type": media_type}


def build_text_query(
    query: str, fields: list[str], serial_prefixes: dict[str, str] | None = None
) -> dict | None:
    """Mongo-filter der kræver at *hvert* ord i `query` findes i mindst ét af
    `fields` (AND mellem ord, OR mellem felter).

    Ord-for-ord frem for én søgning på hele strengen, så "pacino heat" finder
    filmen selvom navn og titel står i hver sit felt. `re.escape` gør at en
    søgning på fx "(2019)" eller "Rock 'n' Roll" behandles som tekst i stedet
    for at blive tolket — eller brække — som et regulært udtryk.

    `serial_prefixes` mapper serie-bogstav til medietype (fx
    `{"M": "Fysisk", "D": "Digital"}`) og slår serienummer-søgning til.

    Returnerer `None` for en tom/whitespace-only søgning, så kalderen kan
    udelade nøglen helt i stedet for at sende et filter der matcher alt.
    """
    terms = query.split()
    if not terms:
        return None

    clauses = []
    for term in terms:
        pattern = re.compile(re.escape(term), re.IGNORECASE)
        # Samme regex mod både streng-felter (title, director) og array-felter
        # (cast, genres) — Mongo matcher automatisk et array hvis mindst ét
        # element matcher, så de to slags felter kan stå side om side her.
        alternatives = [{field: pattern} for field in fields]
        # Feature #95 — serienummeret er en ligeværdig måde at finde en titel
        # på, ikke et særskilt søgefelt: "M42" skal virke i det samme felt
        # som "pacino". Derfor endnu et OR-alternativ frem for en egen
        # parameter i API'et.
        serial_clause = _serial_clause(term, serial_prefixes)
        if serial_clause is not None:
            alternatives.append(serial_clause)
        clauses.append({"$or": alternatives})

    return clauses[0] if len(clauses) == 1 else {"$and": clauses}


async def drop_legacy_text_index(collection) -> None:
    """Fjerner det gamle `$text`-index ved opstart nu hvor intet bruger det.

    Et ubrugt text-index koster skrivetid ved hver eneste opdatering af et
    dokument, og ville forvirre den næste der læser `ensure_indexes` og
    troede søgningen stadig gik gennem det. Idempotent: er indexet allerede
    væk (frisk database), sker der ingenting.
    """
    try:
        indexes = await collection.index_information()
    except Exception:  # pragma: no cover - kun hvis collection ikke findes endnu
        return

    for name, spec in indexes.items():
        # Et text-index har nøglen [("_fts", "text"), ("_ftsx", 1)] — de
        # faktiske felter står i `weights`. Vi genkender det på "text" i
        # nøglen frem for på et forventet navn, så et index oprettet under et
        # andet navn også bliver ryddet op.
        if any(direction == "text" for _, direction in spec.get("key", [])):
            try:
                await collection.drop_index(name)
            except Exception:  # pragma: no cover - fx samtidig opstart
                pass
