from python_workspace_mcp.capabilities import WorkspaceCapabilities


def test_default_capabilities_have_no_outbound_network():
    caps = WorkspaceCapabilities()
    assert caps.outbound_network is False
    assert caps.file_upload is True
    assert caps.file_download is True
    assert caps.package_install is False
