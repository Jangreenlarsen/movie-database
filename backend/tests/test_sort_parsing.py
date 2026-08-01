from app.services.movie_service import parse_sort_param


def test_parse_sort_param_empty_returns_no_levels():
    assert parse_sort_param(None) == []
    assert parse_sort_param("") == []


def test_parse_sort_param_defaults_to_ascending():
    assert parse_sort_param("title") == [("title", 1)]


def test_parse_sort_param_respects_desc():
    assert parse_sort_param("title:desc") == [("title", -1)]


def test_parse_sort_param_supports_up_to_three_levels():
    assert parse_sort_param("format:asc,audio_types:asc,title:desc") == [
        ("format", 1),
        ("audio_types", 1),
        ("title", -1),
    ]


def test_parse_sort_param_caps_at_three_levels():
    assert parse_sort_param("format:asc,audio_types:asc,title:desc,year:asc") == [
        ("format", 1),
        ("audio_types", 1),
        ("title", -1),
    ]


def test_parse_sort_param_drops_unknown_fields():
    assert parse_sort_param("not_a_real_field:asc,title:asc") == [("title", 1)]
