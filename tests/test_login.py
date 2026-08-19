import json

from promki.login import load_access_token


def test_load_access_token_returns_auth_token_cookie(tmp_path):
    session = {
        "cookies": [
            {"name": "authToken", "value": "token-abc", "domain": ".lidl.pl"},
            {"name": "other", "value": "x", "domain": ".lidl.pl"},
        ],
        "origins": [],
    }
    f = tmp_path / "lidl_session.json"
    f.write_text(json.dumps(session))
    assert load_access_token(f) == "token-abc"


def test_load_access_token_no_auth_token_cookie(tmp_path):
    session = {"cookies": [{"name": "other", "value": "x"}], "origins": []}
    f = tmp_path / "lidl_session.json"
    f.write_text(json.dumps(session))
    assert load_access_token(f) is None


def test_load_access_token_empty_auth_token_cookie(tmp_path):
    session = {"cookies": [{"name": "authToken", "value": ""}], "origins": []}
    f = tmp_path / "lidl_session.json"
    f.write_text(json.dumps(session))
    assert load_access_token(f) is None


def test_load_access_token_missing_file(tmp_path):
    assert load_access_token(tmp_path / "nope.json") is None


def test_load_access_token_none_path():
    assert load_access_token(None) is None


def test_load_access_token_invalid_json(tmp_path):
    f = tmp_path / "lidl_session.json"
    f.write_text("{not json")
    assert load_access_token(f) is None


def test_load_access_token_non_object_json(tmp_path):
    for payload in ("null", "[]", '"str"'):
        f = tmp_path / "lidl_session.json"
        f.write_text(payload)
        assert load_access_token(f) is None


def test_load_access_token_skips_non_dict_cookies(tmp_path):
    session = {"cookies": [{"name": "authToken", "value": "ok"}, ["not-a-dict"]]}
    f = tmp_path / "lidl_session.json"
    f.write_text(json.dumps(session))
    assert load_access_token(f) == "ok"
