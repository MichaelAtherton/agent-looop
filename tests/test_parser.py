from agent_looop import parse_input


def test_parse_input_splits_comma_separated_values():
    assert parse_input("alpha, beta,gamma") == ["alpha", "beta", "gamma"]


def test_parse_input_ignores_blank_segments():
    assert parse_input("alpha,, beta, ") == ["alpha", "beta"]
