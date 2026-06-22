from __future__ import annotations

from xiaoai_bridge.init_project import initialize_project


def test_initialize_project_creates_default_files(tmp_path) -> None:
    result = initialize_project(tmp_path)

    assert sorted(path.name for path in result.created) == [".env", ".gitignore", "handler.py"]
    assert result.skipped == []
    assert 'MI_HANDLER="./handler.py:handler"' in (tmp_path / ".env").read_text(encoding="utf-8")
    assert "def handler(question: str, speaker" in (tmp_path / "handler.py").read_text(
        encoding="utf-8",
    )


def test_initialize_project_skips_existing_files(tmp_path) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text("KEEP=1\n", encoding="utf-8")

    result = initialize_project(tmp_path)

    assert env_path in result.skipped
    assert env_path.read_text(encoding="utf-8") == "KEEP=1\n"


def test_initialize_project_force_overwrites_existing_files(tmp_path) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text("KEEP=1\n", encoding="utf-8")

    result = initialize_project(tmp_path, force=True)

    assert env_path in result.created
    assert 'MI_HANDLER="./handler.py:handler"' in env_path.read_text(encoding="utf-8")
