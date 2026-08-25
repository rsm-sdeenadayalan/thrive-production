from rsm_thrive.services.jobs.region import REGION_LABELS, REGION_VALUES, region_of


class TestRegionOf:
    def test_blank_or_none_is_international(self):
        assert region_of("") == "international"
        assert region_of(None) == "international"

    def test_remote_wins_even_when_a_place_is_also_named(self):
        assert region_of("Remote") == "remote"
        assert region_of("Remote - US") == "remote"
        assert region_of("United States - Remote") == "remote"
        assert region_of("Remote Canada") == "remote"

    def test_san_diego(self):
        assert region_of("San Diego, CA") == "san_diego"
        assert region_of("San Diego, United States") == "san_diego"

    def test_bay_area_covers_the_named_cities(self):
        for loc in ("San Francisco, CA", "San Jose, California, USA",
                    "Mountain View, California", "Menlo Park, CA",
                    "Palo Alto, CA", "Oakland, CA"):
            assert region_of(loc) == "bay_area", loc

    def test_los_angeles(self):
        assert region_of("Los Angeles, CA") == "los_angeles"

    def test_seattle_covers_the_metro(self):
        assert region_of("Seattle, Washington") == "seattle"
        assert region_of("Bellevue, Washington") == "seattle"

    def test_new_york(self):
        assert region_of("New York, NY") == "new_york"
        assert region_of("New York, New York, USA") == "new_york"
        assert region_of("New York City, NY") == "new_york"

    def test_other_us_from_state_abbreviation_after_a_comma(self):
        assert region_of("Austin, TX") == "other_us"
        assert region_of("Denver, CO") == "other_us"
        assert region_of("Washington, D.C.") == "other_us"

    def test_other_us_from_full_state_name_or_country_literal(self):
        assert region_of("Charlotte, North Carolina") == "other_us"
        assert region_of("United States") == "other_us"
        assert region_of("Chicago, IL, USA") == "other_us"

    def test_ambiguous_two_letter_words_do_not_false_positive_as_states(self):
        # "OR" (Oregon) and "IN" (Indiana) are also common English words --
        # a bare word-boundary match would wrongly call these "other_us".
        assert region_of("Sydney Or Melbourne") == "international"
        assert region_of("Italy or France or Germany") == "international"
        assert region_of("London OR Dublin") == "international"

    def test_international_for_recognized_foreign_cities(self):
        for loc in ("Tokyo, Japan", "Singapore", "London", "Bengaluru, India",
                    "Sao Paulo, Brazil", "Toronto, Canada", "Paris, France"):
            assert region_of(loc) == "international", loc

    def test_multi_location_string_lands_in_the_first_priority_bucket(self):
        # Remote outranks a named office even when both appear.
        assert region_of("San Francisco, CA | Remote") == "remote"
        # Bay Area outranks New York -- priority order, not string order.
        assert region_of("New York, NY | San Francisco, CA") == "bay_area"

    def test_case_and_period_insensitive(self):
        assert region_of("SAN FRANCISCO, CA") == "bay_area"
        assert region_of("washington, d.c.") == "other_us"


class TestRegionCatalog:
    def test_every_region_value_has_a_label(self):
        assert REGION_VALUES == set(REGION_LABELS)

    def test_region_of_always_returns_a_known_value(self):
        samples = ["", "Remote", "San Diego, CA", "San Francisco, CA",
                   "Los Angeles, CA", "Seattle, WA", "New York, NY",
                   "Austin, TX", "Tokyo, Japan", "gibberish, ZZ"]
        for loc in samples:
            assert region_of(loc) in REGION_VALUES
