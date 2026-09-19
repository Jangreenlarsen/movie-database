"""Feature #223 (Jan: "hvordan kan jeg se hvordan en besked se ud, kan vi
lave en besked design editor hvor alle de besked typer som er i spil kan
se og edit") — read-only katalog over alle besked-typer appen kan sende,
til Indstillinger → Beskeder (admin). Kaldt "design editor" af Jan, men
implementeret som ren VISNING for nu (Jans eksplicitte valg ved
opklarende spørgsmål, 2026-09-19) — ingen gemt redigering endnu. En
fremtidig editerbar udgave er et større, selvstændigt skridt (en rigtig
skabelon-collection som notify_*-funktionerne læser fra i stedet for
hardkodede strenge); denne feature lægger allerede det nødvendige
grundlag ved at have udtrukket hver besked-types tekst til en navngivet
`_content_*`-funktion i message_service.py.

Hvert indslag her kalder PRÆCIS den samme `_content_*`-funktion som den
rigtige notify_*-funktion selv bruger, blot med eksempel-data i stedet
for en rigtig hændelse — previewet kan derfor aldrig vise en anden
ordlyd end den der rent faktisk sendes."""

from app.integrations import email_templates
from app.models.message import MessagePreview
from app.services import message_service as ms

# Eksempel-data, delt af flere indslag nedenfor. Bevidst INGEN ægte ekstern
# URL for posteren (ville kunne rådne/blive utilgængelig) — en lille,
# selvstændig SVG data-URI, så previewet aldrig afhænger af noget uden for
# selve appen.
_SAMPLE_POSTER = (
    "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='140' "
    "height='210'%3E%3Crect width='140' height='210' fill='%23444'/%3E"
    "%3Ctext x='50%25' y='50%25' fill='%23ccc' font-family='sans-serif' "
    "font-size='16' text-anchor='middle' dy='.3em'%3EEksempel%3C/text%3E%3C/svg%3E"
)
_SAMPLE_MOVIE_TITLE = "Dune: Part Two"
_SAMPLE_TV_TITLE = "The Bear"
_SAMPLE_TIE_TITLE = "Arrival"
_SAMPLE_USERNAME = "anna"
_SAMPLE_POLL_TITLE = "Fredagsfilm"
_SAMPLE_WHEN = " d. 12/12/2026 kl. 20:00"
_SAMPLE_REASON = "Vi har den faktisk allerede på Blu-ray i samlingen."


def _entry(key: str, name: str, description: str, content: ms.MessageContent) -> MessagePreview:
    html = (
        email_templates.render_notification_email(**content.html_kwargs)
        if content.html_kwargs is not None
        else None
    )
    return MessagePreview(
        key=key,
        name=name,
        description=description,
        subject=content.subject,
        body=content.body,
        html=html,
    )


def list_message_previews() -> list[MessagePreview]:
    """Ren, synkron opbygning — ingen af `_content_*`-funktionerne rører
    databasen (de tager allerede-resolverede, simple værdier, ikke rå
    dokumenter), så dette kalder ALDRIG `send()` og opretter eller sender
    intet rigtigt."""
    entries = [
        _entry(
            "wishlist_moved",
            "Ønske flyttet til biblioteket",
            "Til den der ønskede titlen, når den er købt og lagt i biblioteket (feature #141).",
            ms._content_wishlist_moved(_SAMPLE_MOVIE_TITLE, False, _SAMPLE_POSTER),
        ),
        _entry(
            "wishlist_approved",
            "Ønske godkendt",
            "Til den der ønskede titlen, når en admin godkender ønsket (feature #166).",
            ms._content_wishlist_approved(_SAMPLE_TV_TITLE, True, _SAMPLE_POSTER),
        ),
        _entry(
            "wishlist_ordered",
            "Ønske bestilt",
            "Til den der ønskede titlen, når en admin markerer den som bestilt (feature #189).",
            ms._content_wishlist_ordered(_SAMPLE_MOVIE_TITLE, False, _SAMPLE_POSTER),
        ),
        _entry(
            "wishlist_rejected",
            "Ønske afvist (med begrundelse)",
            "Til den der ønskede titlen, når en admin afviser ønsket. Uden en begrundelse er brødteksten kortere (kun første linje).",
            ms._content_wishlist_rejected(_SAMPLE_MOVIE_TITLE, False, _SAMPLE_POSTER, _SAMPLE_REASON),
        ),
        _entry(
            "admins_new_wishlist",
            "Admin: nyt ønske",
            "Til alle admins, når en bruger tilføjer en titel til ønskelisten (feature #202). Kun almindelig tekst, ingen e-mail-udgave.",
            ms._content_admins_new_wishlist(_SAMPLE_USERNAME, _SAMPLE_MOVIE_TITLE, False),
        ),
        _entry(
            "admins_new_screening_request",
            "Admin: nyt visnings-ønske",
            "Til alle admins, når en bruger anmoder om en visning i Voldby BIO (feature #202). Kun almindelig tekst.",
            ms._content_admins_new_screening_request(_SAMPLE_USERNAME, _SAMPLE_TV_TITLE, True),
        ),
        _entry(
            "admins_new_poll_suggestion",
            "Admin: nyt afstemnings-forslag",
            "Til alle admins, når en ikke-admin foreslår en ny afstemning (feature #213). Kun almindelig tekst.",
            ms._content_admins_new_poll_suggestion(_SAMPLE_USERNAME, _SAMPLE_POLL_TITLE),
        ),
        _entry(
            "admins_new_candidate_suggestion",
            "Admin: nyt kandidat-forslag",
            "Til alle admins, når nogen foreslår en kandidat til en kørende afstemning (feature #218). Kun almindelig tekst.",
            ms._content_admins_new_candidate_suggestion(_SAMPLE_USERNAME, _SAMPLE_MOVIE_TITLE, _SAMPLE_POLL_TITLE),
        ),
        _entry(
            "poll_candidate_approved",
            "Kandidat-forslag godkendt",
            "Til den der foreslog kandidaten, når en admin godkender forslaget (feature #218).",
            ms._content_poll_candidate_approved(_SAMPLE_MOVIE_TITLE, _SAMPLE_POLL_TITLE),
        ),
        _entry(
            "poll_candidate_rejected",
            "Kandidat-forslag afvist",
            "Til den der foreslog kandidaten, når en admin afviser forslaget (feature #218).",
            ms._content_poll_candidate_rejected(_SAMPLE_MOVIE_TITLE, _SAMPLE_POLL_TITLE),
        ),
        _entry(
            "screening_request_declined",
            "Visnings-anmodning afvist",
            "Til hver anmodningsstiller, når en admin afviser en anmodning om visning (feature #202).",
            ms._content_screening_request_declined(_SAMPLE_MOVIE_TITLE, _SAMPLE_POSTER),
        ),
        _entry(
            "screening_request_scheduled",
            "Visnings-anmodning planlagt",
            "Til anmodningsstiller(e), når en admin planlægger deres ønskede visning (feature #202/#221).",
            ms._content_screening_request_scheduled(_SAMPLE_MOVIE_TITLE, _SAMPLE_WHEN, _SAMPLE_POSTER),
        ),
        _entry(
            "screening_scheduled_broadcast",
            "Visning planlagt — til alle",
            "Alternativ til ovenstående: sendt til ALLE aktive brugere i stedet for kun anmodningsstiller(e), når admin vælger \"Send til alle brugere\" (feature #221).",
            ms._content_screening_scheduled_broadcast(_SAMPLE_MOVIE_TITLE, _SAMPLE_WHEN, _SAMPLE_POSTER),
        ),
        _entry(
            "library_addition_broadcast",
            "Ny titel i samlingen — til alle",
            "Til ALLE aktive brugere, når nogen tilføjer en ny titel til biblioteket og vælger \"Send besked til alle\" (feature #222). Indeholder et link til Voldby BIO.",
            ms._content_library_addition_broadcast(_SAMPLE_MOVIE_TITLE, False, _SAMPLE_POSTER),
        ),
        _entry(
            "poll_closed_single",
            "Afstemning afgjort (én vinder)",
            "Til hver der stemte, når admin lukker afstemningen og der er én entydig vinder (feature #162).",
            ms._content_poll_closed_single(_SAMPLE_MOVIE_TITLE, _SAMPLE_POSTER),
        ),
        _entry(
            "poll_closed_tie",
            "Afstemning afgjort (uafgjort)",
            "Til hver der stemte, når afstemningen ender uafgjort mellem to eller flere kandidater (feature #162).",
            ms._content_poll_closed_tie(f"{_SAMPLE_MOVIE_TITLE}, {_SAMPLE_TIE_TITLE}"),
        ),
        _entry(
            "poll_scheduled",
            "Afstemningsvinder planlagt",
            "Til hver der stemte, når afstemningens vindende titel bliver planlagt til visning (feature #162).",
            ms._content_poll_scheduled(_SAMPLE_MOVIE_TITLE, _SAMPLE_WHEN, _SAMPLE_POSTER),
        ),
        _entry(
            "poll_approved",
            "Afstemnings-forslag godkendt",
            "Til forslagsstilleren, når en admin godkender deres afstemnings-forslag og gør den global (feature #213).",
            ms._content_poll_approved(_SAMPLE_POLL_TITLE),
        ),
        _entry(
            "poll_suggestion_rejected",
            "Afstemnings-forslag afvist",
            "Til forslagsstilleren, når en admin afviser deres afstemnings-forslag (feature #213).",
            ms._content_poll_suggestion_rejected(_SAMPLE_POLL_TITLE),
        ),
    ]

    # Feature #216 — alle 5 faste "aflyst"-varianter, ikke kun én tilfældig,
    # så Jan reelt kan se hele puljen (samme pulje som notify_poll_cancelled
    # vælger tilfældigt fra ved en rigtig afsendelse).
    for index, variant_body in enumerate(ms._POLL_CANCELLED_MESSAGES, start=1):
        entries.append(
            _entry(
                f"poll_cancelled_{index}",
                f"Afstemning aflyst — variant {index}/{len(ms._POLL_CANCELLED_MESSAGES)}",
                "Til hver der stemte, når en admin sletter en endnu åben afstemning (feature #216). "
                f"Én af {len(ms._POLL_CANCELLED_MESSAGES)} tilfældige varianter vælges ved en rigtig afsendelse.",
                ms._content_poll_cancelled(variant_body),
            )
        )

    return entries
