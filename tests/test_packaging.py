import tomllib
from pathlib import Path


def test_pyproject_includes_python_multipart_and_package_discovery():
    pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
    data = tomllib.loads(pyproject.read_text(encoding="utf-8"))

    dependencies = data["project"]["dependencies"]
    assert any(dep.startswith("python-multipart") for dep in dependencies)

    include = data["tool"]["setuptools"]["packages"]["find"]["include"]
    assert "app*" in include
