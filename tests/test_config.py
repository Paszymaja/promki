from promki.config import Config


def test_lidl_session_file_relative_to_project_root(tmp_path):
    config = Config(project_root=tmp_path)
    assert config.lidl_session_file == tmp_path / "lidl_session.json"


def test_kaufland_session_file_relative_to_project_root(tmp_path):
    config = Config(project_root=tmp_path)
    assert config.kaufland_session_file == tmp_path / "kaufland_session.json"


def test_db_file_relative_to_project_root(tmp_path):
    config = Config(project_root=tmp_path)
    assert config.db_file == tmp_path / "coupons.db"
