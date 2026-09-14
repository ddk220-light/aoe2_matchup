from overlay.auto_alignment import anchor_matches


def test_observed_event_rejects_plausible_hp_fit_at_wrong_time():
    anchors=[{'gameSeconds':4.876,'videoMinSeconds':1.70,'videoMaxSeconds':1.80}]
    assert anchor_matches(2, -.73, anchors)
    assert not anchor_matches(1.7, -1.6967, anchors)


def test_all_measured_intervals_must_agree_and_unanchored_search_is_unchanged():
    anchors=[{'gameSeconds':4,'videoMinSeconds':1,'videoMaxSeconds':1.1},
             {'gameSeconds':8,'videoMinSeconds':3,'videoMaxSeconds':3.1}]
    assert anchor_matches(2, -1, anchors)
    assert not anchor_matches(1.7, -1.3, anchors)
    assert anchor_matches(1.7, -3, [])
