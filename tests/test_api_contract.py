from python_workspace_mcp import main
from python_workspace_mcp.main import _decode_path, _encode_path, get_system_info, get_workspaces


def setup_module(module):
    # The server no longer creates its configured user automatically; a real
    # deployment provisions it via `python-workspace user add` before start.
    try:
        main.users.get(main.settings.user_id)
    except ValueError:
        main.users.create_user(main.settings.user_id, main.settings.user_name)


def test_file_path_encoding_round_trips():
    path = "output/my plot.png"
    assert _decode_path(_encode_path(path)) == path


def test_phase1_workspace_contract():
    result = get_workspaces()
    assert len(result["workspaces"]) == 1
    assert result["default_workspace_id"] == result["workspaces"][0]["id"]


def test_system_info_exposes_stable_api_metadata():
    result = get_system_info()
    assert result["api_version"] == "1"
    assert result["transport"] == "streamable-http"
    assert result["deployment_profile"] == "local"
    assert result["runtime"]["execution_backend"] == "docker"
