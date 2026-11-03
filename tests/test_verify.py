from src.agents.verify import check_numbers

F = [{"rows": [["2024", "483935.12"], ["2025", "521307.59"]]}]


def test_accepts_amounts_and_their_difference():
    assert check_numbers("Revenue was $483,935.12 then $521,307.59, up $37,372.47.", F) == []


def test_flags_invented_amount():
    assert check_numbers("Revenue was $999,999.00.", F) == ["$999,999.00"]
