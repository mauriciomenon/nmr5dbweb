import sys
import types
import errno

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
    setattr(fake_module, "app", FakeApp())
    monkeypatch.setitem(sys.modules, "interface.app_flask_local_search", fake_module)

    with pytest.raises(SystemExit) as exc:
        app_main.main()

    assert exc.value.code == 0
    assert calls["kwargs"]["port"] == 5001
    assert calls["kwargs"]["host"] == "127.0.0.1"


def test_main_port_fallback_desativado(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["main.py", "--no-port-fallback"])
    monkeypatch.setattr(app_main, "validar_configuracao", lambda _args: [])
    monkeypatch.setattr(app_main, "verificar_porta_disponivel", lambda _host, _port: False)
    monkeypatch.setattr(app_main, "obter_processo_na_porta", lambda _port: None)

    with pytest.raises(SystemExit) as exc:
        app_main.main()

    assert exc.value.code == 1
    captured = capsys.readouterr().out
    assert "Fallback de porta desativado" in captured


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
    setattr(fake_module, "app", FakeApp())
    monkeypatch.setitem(sys.modules, "interface.app_flask_local_search", fake_module)

    with pytest.raises(SystemExit) as exc:
        app_main.main()

    assert exc.value.code == 0
    assert calls["kwargs"]["port"] == 5000


def test_encontrar_proxima_porta_livre_pula_portas_ocupadas(monkeypatch):
    def fake_verificar(_host, porta):
        return int(porta) == 5002

    monkeypatch.setattr(app_main, "verificar_porta_disponivel", fake_verificar)
    assert app_main.encontrar_proxima_porta_livre("127.0.0.1", 5000, max_tentativas=5) == 5002


def test_main_bind_error_porta_em_uso(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["main.py"])
    monkeypatch.setattr(app_main, "validar_configuracao", lambda _args: [])
    monkeypatch.setattr(app_main, "verificar_porta_disponivel", lambda _host, _port: True)
    monkeypatch.setattr(app_main, "configurar_logging", lambda: None)

    class FakeApp:
        config = {}

        def run(self, **_kwargs):
            raise OSError(errno.EADDRINUSE, "Address already in use")

    fake_module = types.ModuleType("interface.app_flask_local_search")
    setattr(fake_module, "app", FakeApp())
    monkeypatch.setitem(sys.modules, "interface.app_flask_local_search", fake_module)

    with pytest.raises(SystemExit) as exc:
        app_main.main()

    assert exc.value.code == 1
    captured = capsys.readouterr().out
    assert "porta ja esta em uso" in captured


def test_main_bind_error_generico(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["main.py"])
    monkeypatch.setattr(app_main, "validar_configuracao", lambda _args: [])
    monkeypatch.setattr(app_main, "verificar_porta_disponivel", lambda _host, _port: True)
    monkeypatch.setattr(app_main, "configurar_logging", lambda: None)

    class FakeApp:
        config = {}

        def run(self, **_kwargs):
            raise OSError(errno.EACCES, "Permission denied")

    fake_module = types.ModuleType("interface.app_flask_local_search")
    setattr(fake_module, "app", FakeApp())
    monkeypatch.setitem(sys.modules, "interface.app_flask_local_search", fake_module)

    with pytest.raises(SystemExit) as exc:
        app_main.main()

    assert exc.value.code == 1
    captured = capsys.readouterr().out
    assert "Falha de sistema operacional durante inicializacao" in captured


def test_main_preserva_upload_folder_do_env_quando_sem_flag(monkeypatch):
    calls = {}

    monkeypatch.setattr(sys, "argv", ["main.py"])
    monkeypatch.setenv("UPLOAD_FOLDER", "/tmp/upload-env")
    monkeypatch.setattr(app_main, "validar_configuracao", lambda _args: [])
    monkeypatch.setattr(app_main, "verificar_porta_disponivel", lambda _host, _port: True)
    monkeypatch.setattr(app_main, "configurar_logging", lambda: None)

    class FakeApp:
        config = {}

        def run(self, **kwargs):
            calls["kwargs"] = kwargs
            raise KeyboardInterrupt

    fake_module = types.ModuleType("interface.app_flask_local_search")
    setattr(fake_module, "app", FakeApp())
    monkeypatch.setitem(sys.modules, "interface.app_flask_local_search", fake_module)

    with pytest.raises(SystemExit) as exc:
        app_main.main()

    assert exc.value.code == 0
    assert app_main.os.environ["UPLOAD_FOLDER"] == "/tmp/upload-env"
    assert calls["kwargs"]["port"] == 5000


def test_main_usa_runtime_dir_fora_do_repo_por_padrao(monkeypatch, tmp_path):
    calls = {}
    runtime_dir = tmp_path / "runtime"

    monkeypatch.setattr(sys, "argv", ["main.py"])
    monkeypatch.delenv("UPLOAD_FOLDER", raising=False)
    monkeypatch.setenv("NMR5DBWEB_DATA_DIR", str(runtime_dir))
    monkeypatch.setattr(app_main, "validar_configuracao", lambda _args: [])
    monkeypatch.setattr(app_main, "verificar_porta_disponivel", lambda _host, _port: True)
    monkeypatch.setattr(app_main, "configurar_logging", lambda: None)

    class FakeApp:
        config = {}

        def run(self, **kwargs):
            calls["kwargs"] = kwargs
            raise KeyboardInterrupt

    fake_module = types.ModuleType("interface.app_flask_local_search")
    setattr(fake_module, "app", FakeApp())
    monkeypatch.setitem(sys.modules, "interface.app_flask_local_search", fake_module)

    with pytest.raises(SystemExit) as exc:
        app_main.main()

    assert exc.value.code == 0
    assert app_main.os.environ["UPLOAD_FOLDER"] == str(runtime_dir / "documentos")
    assert calls["kwargs"]["port"] == 5000
