from harbor import mcp_server


def test_mcp_tools_import_without_optional_dependency():
    cat = mcp_server.harbor_worker_catalog()
    assert "newsletter-intelligence" in cat
