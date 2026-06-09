"""Unit tests for Tier A network offense (no targets/deps; clients injected)."""
from offense.net_offense import DEFAULT_PASSWORDS, DEFAULT_USERS, load_wordlists


def test_default_wordlists_nonempty():
    assert "root" in DEFAULT_USERS
    assert "admin" in DEFAULT_USERS
    assert len(DEFAULT_PASSWORDS) >= 5
    users, passwords = load_wordlists()
    assert users == DEFAULT_USERS
    assert passwords == DEFAULT_PASSWORDS


def test_wordlist_config_override(tmp_path):
    ul = tmp_path / "u.txt"; ul.write_text("alice\nbob\n", encoding="utf-8")
    pl = tmp_path / "p.txt"; pl.write_text("hunter2\n\n  spaces  \n", encoding="utf-8")
    users, passwords = load_wordlists({"bruteforce": {"userlist": str(ul),
                                                      "passlist": str(pl)}})
    assert users == ["alice", "bob"]
    assert passwords == ["hunter2", "spaces"]      # blank lines dropped, trimmed
