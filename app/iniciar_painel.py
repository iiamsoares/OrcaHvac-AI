import os
import sys
import subprocess
import webbrowser
import time

def main():
    root_dir = r"c:\Users\Tecnologia\Agente - Setor Orçamentos\catalogoIA"
    dashboard_dir = os.path.join(root_dir, "dashboard")
    env_root = os.path.join(root_dir, ".env")
    env_dashboard = os.path.join(dashboard_dir, ".env")
    
    print("=== INICIALIZADOR DO PAINEL REACT ===")
    
    # 1. Ler as credenciais do .env raiz
    if not os.path.exists(env_root):
        print(f"[Erro] Arquivo .env raiz não encontrado em: {env_root}")
        sys.exit(1)
        
    supabase_url = ""
    supabase_key = ""
    supabase_service_role = ""
    
    with open(env_root, 'r', encoding='utf-8') as f:
        for line in f:
            if '=' in line:
                key, val = line.strip().split('=', 1)
                key = key.strip()
                val = val.strip().strip('"').strip("'")
                if key == "SUPABASE_URL":
                    supabase_url = val
                elif key == "SUPABASE_KEY":
                    supabase_key = val
                elif key == "SUPABASE_SERVICE_ROLE_KEY":
                    supabase_service_role = val
                    
    active_key = supabase_service_role or supabase_key
    
    if not supabase_url or not active_key:
        print("[Erro] SUPABASE_URL ou chaves de autenticação do Supabase não configuradas no .env raiz.")
        sys.exit(1)
        
    # 2. Escrever o .env do dashboard
    os.makedirs(dashboard_dir, exist_ok=True)
    with open(env_dashboard, 'w', encoding='utf-8') as f:
        f.write(f"VITE_SUPABASE_URL={supabase_url}\n")
        f.write(f"VITE_SUPABASE_ANON_KEY={active_key}\n")
    print("-> Credenciais copiadas com sucesso para dashboard/.env")
    
    # 3. Atualizar dados locais JSON
    print("-> Atualizando dados locais de catálogos (PDFs)...")
    
    # Tentar encontrar e usar o Python do ambiente virtual (.venv) para carregar os pacotes corretos (ex: fitz)
    venv_python = os.path.join(root_dir, ".venv", "Scripts", "python.exe")
    if not os.path.exists(venv_python):
        venv_python = os.path.join(root_dir, ".venv", "bin", "python")
        
    python_exe = venv_python if os.path.exists(venv_python) else sys.executable
    
    script_gerar = os.path.join(root_dir, "app", "gerar_dados_locais.py")
    try:
        subprocess.run([python_exe, script_gerar], check=True)
    except subprocess.CalledProcessError as err:
        print(f"[Erro] Falha ao executar gerar_dados_locais.py: {err}")
        sys.exit(1)
        
    # 4. Verificar node_modules e npm install
    node_modules_path = os.path.join(dashboard_dir, "node_modules")
    if not os.path.exists(node_modules_path):
        print("-> Primeira execução detectada. Instalando dependências (npm install)...")
        try:
            # shell=True é necessário no Windows para rodar comandos como 'npm'
            subprocess.run("npm install", cwd=dashboard_dir, shell=True, check=True)
            print("-> Dependências instaladas com sucesso!")
        except subprocess.CalledProcessError as err:
            print(f"[Erro] Falha ao rodar npm install: {err}")
            sys.exit(1)
            
    # 5. Iniciar o servidor dev (Vite)
    print("\n-> Iniciando servidor do dashboard (npm run dev)...")
    
    # Abre o navegador após 3 segundos
    def open_browser():
        time.sleep(3)
        print("-> Abrindo o navegador em http://localhost:5173...")
        webbrowser.open("http://localhost:5173")
        
    import threading
    threading.Thread(target=open_browser, daemon=True).start()
    
    try:
        subprocess.run("npm run dev", cwd=dashboard_dir, shell=True)
    except KeyboardInterrupt:
        print("\nServidor encerrado pelo usuário.")

if __name__ == "__main__":
    main()
