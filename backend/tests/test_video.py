from recetary.extraction.video import _extract_instagram_shortcode


def test_extract_instagram_shortcode_with_username():
    url = "https://www.instagram.com/charlito_cooks/reel/DdYSgFBAoby/"
    assert _extract_instagram_shortcode(url) == "DdYSgFBAoby"


def test_extract_instagram_shortcode_without_username():
    url = "https://www.instagram.com/reel/DdYSgFBAoby/"
    assert _extract_instagram_shortcode(url) == "DdYSgFBAoby"
