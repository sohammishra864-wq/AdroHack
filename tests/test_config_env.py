""".env loading: values land in os.environ, the shell wins, empty values and comments are skipped."""
from claimshield import config


def test_load_env(tmp_path, monkeypatch):
    for k in ("CS_A", "CS_B", "CS_EMPTY", "CS_SHELL"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("CS_SHELL", "from-shell")
    env = tmp_path / ".env"
    env.write_text('# comment\nCS_A=1\nCS_B="quoted value"\nCS_EMPTY=\nCS_SHELL=from-file\n# CS_C=no\n',
                   encoding="utf-8")
    config.load_env(env)
    import os
    assert os.environ["CS_A"] == "1" and os.environ["CS_B"] == "quoted value"
    assert "CS_EMPTY" not in os.environ and "CS_C" not in os.environ
    assert os.environ["CS_SHELL"] == "from-shell"
