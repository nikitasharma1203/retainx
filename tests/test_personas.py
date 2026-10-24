from src import personas
from tests.synth import make_orders


def test_personas_profile_and_prompt():
    f, prof, sil, k = personas.build_personas(make_orders(900, seed=6), "2011-06-01")
    assert k in sil and 2 <= k <= 8
    assert abs(prof["share_customers"].sum() - 1) < 1e-9
    assert abs(prof["share_revenue"].sum() - 1) < 1e-9
    assert "Do not invent demographics" in personas.prompt_for_claude(prof)


def test_personas_k_can_be_forced():
    f, prof, sil, k = personas.build_personas(make_orders(900, seed=6), "2011-06-01", force_k=4)
    assert k == 4 and len(prof) == 4
