from app.integrations.text_cleanup import clean_bracketed_title


def test_strips_bracketed_suffix():
    assert clean_bracketed_title("The Matrix (DVD)") == "The Matrix"
    assert clean_bracketed_title("The Matrix [Blu-ray]") == "The Matrix"
    assert clean_bracketed_title("The Matrix (1999)") == "The Matrix"


def test_strips_unbracketed_edition_boilerplate():
    assert clean_bracketed_title("The Matrix Special Edition") == "The Matrix"
    assert clean_bracketed_title("Inception Director's Cut") == "Inception"
    assert clean_bracketed_title("Blade Runner Remastered") == "Blade Runner"


def test_strips_unbracketed_format_words():
    assert clean_bracketed_title("The Matrix DVD") == "The Matrix"
    assert clean_bracketed_title("The Matrix Blu-ray") == "The Matrix"
    assert clean_bracketed_title("The Matrix 4K UHD") == "The Matrix"


def test_strips_box_set_and_season_boilerplate():
    """Regression test for BUGS.md #20 — the exact real-world title that
    prompted this fix. Note: TMDb still won't find a *movie* match for "The
    Americans" since it's a TV series (out of scope for this app), but the
    cleaned query is now what actually gets searched instead of the noisy
    original, which is the fixable part."""
    assert (
        clean_bracketed_title("The Americans Complete Series Seasons 1-6 (dvd 2018)")
        == "The Americans"
    )
    assert clean_bracketed_title("Star Wars Trilogy Collection") == "Star Wars"
    assert clean_bracketed_title("Friends Complete Collection Box Set") == "Friends"


def test_does_not_eat_real_title_words():
    """The boilerplate list is word-boundaried and phrase-specific — it
    must not strip legitimate title content that merely contains a
    substring of a boilerplate term."""
    assert clean_bracketed_title("Specialist") == "Specialist"
    assert clean_bracketed_title("Region") == "Region"


def test_collapses_whitespace_and_trims():
    assert clean_bracketed_title("  The Matrix   (DVD)  ") == "The Matrix"


def test_empty_and_plain_titles_are_unaffected():
    assert clean_bracketed_title("The Matrix") == "The Matrix"
    assert clean_bracketed_title("") == ""


def test_strips_trailing_dash_number_disc_index():
    """Regression test found 2026-08-04 in production logs: EAN-Search.org's
    "Simply HE The Americans - 6" (a disc/season index the retailer tacked
    on) returned zero TMDb candidates as a whole string."""
    assert clean_bracketed_title("Simply HE The Americans - 6") == "Simply HE The Americans"
    assert clean_bracketed_title("Rocky - 2") == "Rocky"
    assert clean_bracketed_title("Rocky – 2") == "Rocky"


def test_does_not_strip_number_that_is_part_of_the_title():
    """A trailing number with no dash separator, or a word between the dash
    and the number, is real title content — not a disc/season index."""
    assert clean_bracketed_title("Blade Runner 2049") == "Blade Runner 2049"
    assert clean_bracketed_title("300") == "300"
    assert clean_bracketed_title("Kill Bill - Vol. 1") == "Kill Bill - Vol. 1"
