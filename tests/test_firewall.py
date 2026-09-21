from unittest.mock import Mock

from app import server_config


def test_firewall_rule_is_replaced_with_the_selected_port(monkeypatch):
    run = Mock(return_value=Mock(returncode=0, stdout="", stderr=""))
    monkeypatch.setattr(server_config.os, "name", "nt")
    monkeypatch.setattr(server_config.subprocess, "run", run)

    server_config.configure_windows_firewall(4789)

    assert run.call_count == 2
    delete_command = run.call_args_list[0].args[0]
    add_command = run.call_args_list[1].args[0]
    assert delete_command[-1] == f"name={server_config.FIREWALL_RULE_NAME}"
    assert "localport=4789" in add_command
