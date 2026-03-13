import sys
import types

import pytest

import main as app_main


def test_main_port_fallback_automatico(monkeypatch):
    calls = {}

    monkeypatch.setattr(sys, "argv", ["main.py"])
    monkeypatch.setattr(app_main, "validar_configuracao", lambda _args: [])
    monkeypatch.setattr(app_main, "verificar_porta_disponivel", lambda _host, _port: False)
    monkeypatch.setattr(app_main, "obter_processo_na_porta", lambda _port: {"pid": 123, "name": "proc"})
    monkeypatch.setattr(app_main, "encontrar_proxima_porta_livre", lambda _host, _port, max_tentativas=50: 5001)
    monkeypatch.setattr(app_main, "configurar_logging", lambda: None)

    class FakeApp:
        config = {}

        def run(self, **kwargs):
            calls["kwargs"] = kwargs
            raise KeyboardInterrupt

    fake_module = types.ModuleType("interface.app_flask_local_search")
    fake_module.app = FakeApp()
    monkeypatch.setitem(sys.modules, "interface.app_flask_local_search", fake_module)

    with pytest.raises(SystemExit) as exc:
        app_main.main()

    assert exc.value.code == 0
    assert calls["kwargs"]["port"] == 5001
    assert calls["kwargs"]["host"] == "127.0.0.1"


def test_main_port_fallback_desativado(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["main.py", "--no-port-fallback"])
    monkeypatch.setattr(app_main, "validar_configuracao", lambda _args: [])
    monkeypatch.setattr(app_main, "verificar_porta_disponivel", lambda _host, _port: False)
    monkeypatch.setattr(app_main, "obter_processo_na_porta", lambda _port: None)

    with pytest.raises(SystemExit) as exc:
        app_main.main()

    assert exc.value.code == 1


def test_main_port_livre_mantem_porta(monkeypatch):
    calls = {}

    monkeypatch.setattr(sys, "argv", ["main.py"])
    monkeypatch.setattr(app_main, "validar_configuracao", lambda _args: [])
    monkeypatch.setattr(app_main, "verificar_porta_disponivel", lambda _host, _port: True)
    monkeypatch.setattr(app_main, "configurar_logging", lambda: None)

    class FakeApp:
        config = {}

        def run(self, **kwargs):
            calls["kwargs"] = kwargs
            raise KeyboardInterrupt

    fake_module = types.ModuleType("interface.app_flask_local_search")
    fake_module.app = FakeApp()
    monkeypatch.setitem(sys.modules, "interface.app_flask_local_search", fake_module)

    with pytest.raises(SystemExit) as exc:
        app_main.main()

    assert exc.value.code == 0
    assert calls["kwargs"]["port"] == 5000
