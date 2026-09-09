from app.services.near_duplicates import NearDupCandidate, compute_near_duplicate_clusters

BASE_TEXT = (
    "Please review the attached quarterly budget proposal before Friday's meeting "
    "and send any comments to the finance team as soon as possible so we can "
    "finalize the numbers ahead of the board presentation next week. This draft "
    "reflects the updated hiring plan and the revised marketing spend we discussed "
    "on the call yesterday, along with the vendor contract renewals due next month "
    "and the office lease renegotiation the facilities team has been tracking since "
    "the start of the quarter, so please flag anything that looks off before we "
    "circulate this more broadly to the rest of the leadership team on Monday."
)


def test_near_identical_documents_cluster_together():
    almost_same = BASE_TEXT.replace("Friday's", "Thursday's")
    candidates = [
        NearDupCandidate(id="1", text=BASE_TEXT),
        NearDupCandidate(id="2", text=almost_same),
        NearDupCandidate(id="3", text="Completely unrelated text about a picnic in the park."),
    ]
    assignments = {a.id: a.cluster_key for a in compute_near_duplicate_clusters(candidates)}
    assert assignments["1"] is not None
    assert assignments["1"] == assignments["2"]
    assert assignments["3"] is None


def test_unrelated_documents_are_singletons():
    candidates = [
        NearDupCandidate(id="1", text="The quick brown fox jumps over the lazy dog."),
        NearDupCandidate(id="2", text="Quarterly revenue exceeded expectations this year."),
    ]
    assignments = {a.id: a.cluster_key for a in compute_near_duplicate_clusters(candidates)}
    assert assignments["1"] is None
    assert assignments["2"] is None


def test_empty_text_is_never_clustered():
    candidates = [
        NearDupCandidate(id="1", text=""),
        NearDupCandidate(id="2", text="   "),
        NearDupCandidate(id="3", text=BASE_TEXT),
    ]
    assignments = {a.id: a.cluster_key for a in compute_near_duplicate_clusters(candidates)}
    assert assignments["1"] is None
    assert assignments["2"] is None


def test_three_way_near_duplicate_cluster_shares_one_key():
    variant_a = BASE_TEXT.replace("Friday's", "Thursday's")
    variant_b = BASE_TEXT.replace("Monday.", "Tuesday.")
    candidates = [
        NearDupCandidate(id="1", text=BASE_TEXT),
        NearDupCandidate(id="2", text=variant_a),
        NearDupCandidate(id="3", text=variant_b),
    ]
    assignments = {a.id: a.cluster_key for a in compute_near_duplicate_clusters(candidates)}
    assert assignments["1"] == assignments["2"] == assignments["3"]
    assert assignments["1"] is not None


def test_quoted_reply_lines_are_stripped_before_comparison():
    new_body = "Sounds good, let's go with the revised numbers."
    quoted_history = "\n".join(f"> {word}" for word in BASE_TEXT.split(" "))
    quoted = f"{new_body}\n\nOn Tue, Jan 1 wrote:\n{quoted_history}"
    candidates = [
        NearDupCandidate(id="1", text=new_body),
        NearDupCandidate(id="2", text=quoted),
    ]
    assignments = {a.id: a.cluster_key for a in compute_near_duplicate_clusters(candidates)}
    assert assignments["1"] == assignments["2"]
    assert assignments["1"] is not None


def test_rejects_non_divisible_band_configuration():
    import pytest

    with pytest.raises(ValueError):
        compute_near_duplicate_clusters(
            [NearDupCandidate(id="1", text=BASE_TEXT)], num_hashes=64, num_bands=10
        )
