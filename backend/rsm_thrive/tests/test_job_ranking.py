from rsm_thrive.services.jobs.ranking import rank_score, title_match_score


class TestTitleMatchScore:
    def test_empty_query_never_matches(self):
        assert title_match_score("", "Data Analyst") == 0.0
        assert title_match_score("   ", "Data Analyst") == 0.0

    def test_exact_title_scores_top_tier(self):
        assert title_match_score("data analyst", "Data Analyst") == 1.0

    def test_near_exact_title_ignores_seniority_and_level_words(self):
        assert title_match_score("data analyst", "Senior Data Analyst II") == 1.0
        assert title_match_score("data analyst", "Junior Data Analyst") == 1.0
        assert title_match_score("data analyst", "Lead Data Analyst") == 1.0

    def test_title_reordered_is_still_near_exact_once_normalized(self):
        # Token-set equality, not a literal string match -- word order in a
        # title should not defeat the near-exact tier.
        assert title_match_score("analyst data", "Data Analyst") == 1.0

    def test_all_terms_present_but_extra_words_scores_second_tier(self):
        score = title_match_score("data analyst", "Data Analyst, Growth Team")
        assert score == 0.75

    def test_partial_term_overlap_scores_below_second_tier(self):
        # Only "analyst" of the two query terms appears in the title.
        score = title_match_score("data analyst", "Senior Workday Analyst, Payroll")
        assert 0.0 < score < 0.75
        assert score == 0.25  # 0.5 * (1 matched / 2 terms)

    def test_no_term_overlap_scores_zero(self):
        assert title_match_score("data analyst", "Executive Chef") == 0.0

    def test_case_and_punctuation_insensitive(self):
        assert title_match_score("Data Analyst", "DATA-ANALYST") == 1.0


class TestRankScore:
    def test_reproduces_the_reported_failure(self):
        """The bug report, verbatim: for the query "data analyst", a genuine
        Data Analyst posting with middling resume fit must outrank a
        "Senior Workday Analyst, Payroll" posting with high resume-skill
        overlap -- title relevance has to dominate, but resume fit still
        has to matter as the tiebreaker (see the weight assertions below).
        """
        data_analyst = rank_score("data analyst", "Data Analyst", resume_fit=0.5)
        workday_analyst = rank_score(
            "data analyst", "Senior Workday Analyst, Payroll", resume_fit=0.9)

        assert data_analyst > workday_analyst

    def test_title_match_beats_resume_fit_alone_would_predict(self):
        # A perfect title match with WORSE resume fit than a poor title
        # match must still win -- this is the whole point of the fix.
        good_title = rank_score("data analyst", "Data Analyst", resume_fit=0.3)
        bad_title = rank_score("data analyst", "Warehouse Associate", resume_fit=0.95)
        assert good_title > bad_title

    def test_resume_fit_still_breaks_ties_between_equal_titles(self):
        stronger = rank_score("data analyst", "Data Analyst", resume_fit=0.8)
        weaker = rank_score("data analyst", "Data Analyst", resume_fit=0.2)
        assert stronger > weaker

    def test_weights_sum_to_one_so_the_scale_stays_0_to_1(self):
        from rsm_thrive.services.jobs.ranking import RESUME_FIT_WEIGHT, TITLE_WEIGHT
        assert TITLE_WEIGHT + RESUME_FIT_WEIGHT == 1.0
        assert rank_score("data analyst", "Data Analyst", resume_fit=1.0) == 1.0
        assert rank_score("data analyst", "Executive Chef", resume_fit=0.0) == 0.0

    def test_empty_query_falls_back_to_pure_resume_fit_ordering(self):
        # No query terms -- title contributes nothing, so relative order
        # between two postings must track resume fit alone.
        higher = rank_score("", "Executive Chef", resume_fit=0.9)
        lower = rank_score("", "Data Analyst", resume_fit=0.1)
        assert higher > lower
