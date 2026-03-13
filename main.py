#!/usr/bin/env python3
"""
MDB2SQL - Interface Principal

Script principal para executar a interface web Flask de conversão e busca MDB2SQL.
Ultima modificacao: 2025-12-29T14:30:00
"""

import os
import sys
import argparse
import socket
from pathlib import Path
from datetime import datetime


def verificar_porta_disponivel(host, porta):
    """Verifica se a porta esta disponivel para uso."""
    try:
        family = socket.AF_INET6 if ":" in str(host) else socket.AF_INET
        with socket.socket(family, socket.SOCK_STREAM) as s:
            s.bind((host, porta))
        return True
    except OSError:
        return False


def obter_processo_na_porta(porta):
    """Retorna informacoes basicas do processo que esta escutando na porta."""
    try:
        import psutil
    except Exception:
        return None

    try:
        for conn in psutil.net_connections(kind="tcp"):
            if conn.status != psutil.CONN_LISTEN:
                continue
            if not conn.laddr:
                continue
            if int(conn.laddr.port) != int(porta):
                continue
            pid = conn.pid
            nome = ""
            if pid:
                try:
                    nome = psutil.Process(pid).name()
                except Exception:
                    nome = ""
            return {"pid": pid, "name": nome}
    except Exception:
        return None
    return None


def encontrar_proxima_porta_livre(host, porta_inicial, max_tentativas=30):
    """Procura a proxima porta livre a partir de porta_inicial + 1."""
    porta = int(porta_inicial)
    for _ in range(max_tentativas):
        porta += 1
        if porta > 65535:
            break
        if verificar_porta_disponivel(host, porta):
            return porta
    return None


def validar_configuracao(args):
    """Valida a configuração antes de iniciar o servidor."""
    erros = []

    # Validar porta
    if not 1 <= args.port <= 65535:
        erros.append(f"Porta invalida: {args.port}. Deve estar entre 1 e 65535")

    # Validar pasta de uploads
    if args.upload_folder:
        upload_path = Path(args.upload_folder)
        if not upload_path.exists():
            try:
                upload_path.mkdir(parents=True, exist_ok=True)
            except PermissionError:
                erros.append(f"Sem permissao para criar pasta: {args.upload_folder}")
        elif not upload_path.is_dir():
            erros.append(f"Caminho nao e uma pasta: {args.upload_folder}")

    # Validar tamanho máximo
    if args.max_content_length <= 0:
        erros.append("Tamanho maximo de upload deve ser maior que zero")

    return erros


def configurar_logging():
    """Configura o sistema de logging."""
    # Configurar para suprimir warnings de dependencias
    os.environ["PYTHONWARNINGS"] = "ignore"

    # Configurar Flask para modo menos verboso em producao
    if not os.environ.get("FLASK_DEBUG") == "True":
        os.environ["FLASK_ENV"] = "production"


def main():
    parser = argparse.ArgumentParser(
        description="MDB2SQL - Interface Web Flask",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos de uso:
  python main.py                    # Executar com configuracoes padrao
  python main.py --debug            # Modo desenvolvimento
  python main.py --port 8080        # Usar porta diferente
  python main.py --host 0.0.0.0     # Acessivel de qualquer IP
        """,
    )

    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host para rodar o servidor (padrao: 127.0.0.1)",
    )
    parser.add_argument(
        "--port", type=int, default=5000, help="Porta do servidor (padrao: 5000)"
    )
    parser.add_argument("--debug", action="store_true", help="Ativar modo debug")
    parser.add_argument(
        "--upload-folder", help="Pasta para uploads (padrao: interface/uploads)"
    )
    parser.add_argument(
        "--max-content-length",
        type=int,
        default=500 * 1024 * 1024,
        help="Tamanho maximo de upload em bytes (padrao: 500MB)",
    )
    parser.add_argument(
        "--threaded",
        action="store_true",
        default=True,
        help="Usar threads para melhor desempenho (padrao: ativado)",
    )
    parser.add_argument(
        "--no-port-fallback",
        action="store_true",
        help="Nao tenta porta alternativa quando a porta informada estiver ocupada",
    )

    args = parser.parse_args()

    # Gerar timestamp unico para esta execucao
    timestamp_exec = datetime.now().isoformat()

    # Validar configuracao
    erros = validar_configuracao(args)
    if erros:
        print(f"{timestamp_exec} - MDB2SQL - Interface Principal")
        print("Erros de configuracao:")
        for erro in erros:
            print(f"  - {erro}")
        sys.exit(1)

    # Verificar se a porta esta disponivel
    if not verificar_porta_disponivel(args.host, args.port):
        proc = obter_processo_na_porta(args.port)
        print(f"{timestamp_exec} - MDB2SQL - Interface Principal")
        print(f"Aviso: Porta {args.port} ja esta em uso no host {args.host}")
        if proc:
            pid = proc.get("pid")
            nome = proc.get("name") or "processo_desconhecido"
            print(f"Processo detectado na porta: pid={pid} nome={nome}")
        else:
            print("Processo na porta nao identificado")

        if args.no_port_fallback:
            print("Fallback de porta desativado por --no-port-fallback")
            sys.exit(1)

        nova_porta = encontrar_proxima_porta_livre(args.host, args.port, max_tentativas=50)
        if nova_porta is None:
            print("Erro: nao foi encontrada porta livre nas proximas 50 tentativas")
            sys.exit(1)
        print(f"Usando porta alternativa automaticamente: {nova_porta}")
        args.port = nova_porta

    # Configurar variaveis de ambiente
    os.environ["FLASK_HOST"] = args.host
    os.environ["FLASK_PORT"] = str(args.port)
    os.environ["FLASK_DEBUG"] = str(args.debug)

    if args.upload_folder:
        os.environ["UPLOAD_FOLDER"] = args.upload_folder

    os.environ["MAX_CONTENT_LENGTH"] = str(args.max_content_length)

    # Configurar logging
    configurar_logging()

    # Adicionar diretorio raiz ao path
    script_dir = Path(__file__).parent.absolute()
    sys.path.insert(0, str(script_dir))

    # Importar e executar o app Flask
    try:
        from interface.app_flask_local_search import app

        print(f"{timestamp_exec} - MDB2SQL - Interface Principal")
        print("Iniciando servidor Flask")
        print(f"Pasta de uploads: {args.upload_folder or 'interface/uploads'}")
        print(f"Servidor: http://{args.host}:{args.port}")
        print(f"Debug: {'Ativado' if args.debug else 'Desativado'}")
        print(f"Modo threaded: {'Ativado' if args.threaded else 'Desativado'}")
        print("=" * 50)

        # Configuracoes adicionais para melhor desempenho
        app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0 if args.debug else 31536000
        app.config["TEMPLATES_AUTO_RELOAD"] = args.debug

        app.run(
            host=args.host,
            port=args.port,
            debug=args.debug,
            threaded=args.threaded,
            use_reloader=args.debug,  # So usar reloader em debug
        )

    except ImportError as e:
        print(f"{timestamp_exec} - MDB2SQL - Interface Principal")
        print(f"Erro ao importar o modulo Flask: {e}")
        print("Verifique se as dependencias estao instaladas:")
        print("   uv sync --python .venv/bin/python --all-groups")
        sys.exit(1)
    except KeyboardInterrupt:
        print(f"\n{timestamp_exec} - MDB2SQL - Interface Principal")
        print("Servidor interrompido pelo usuario")
        sys.exit(0)
    except OSError as e:
        print(f"{timestamp_exec} - MDB2SQL - Interface Principal")
        print(f"Erro de sistema operacional: {e}")
        if "Address already in use" in str(e):
            print("A porta ja esta em uso por outro processo")
        sys.exit(1)
    except Exception as e:
        print(f"{timestamp_exec} - MDB2SQL - Interface Principal")
        print(f"Erro ao iniciar o servidor: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
