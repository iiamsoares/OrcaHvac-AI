# Guia de Configuração e Execução - catalogoIA

Este guia explica os passos necessários para configurar o banco de dados Supabase, preencher as credenciais e rodar o projeto localmente.

---

## 1. Configurar o Supabase

1. Crie uma conta/projeto no [Supabase](https://supabase.com/).
2. Vá em **SQL Editor** no menu lateral esquerdo do painel do seu projeto.
3. Clique em **New Query** (Nova consulta).
4. Abra o arquivo [esquema.sql](file:///C:/Users/Tecnologia/Agente%20-%20Setor%20Or%C3%A7amentos/catalogoIA/banco/esquema.sql), copie todo o seu conteúdo e cole no SQL Editor do Supabase.
5. Clique em **Run** (Executar) para criar a tabela, políticas de segurança e a função de busca por similaridade.

---

## 2. Configurar as Credenciais (.env)

Abra o arquivo [.env](file:///C:/Users/Tecnologia/Agente%20-%20Setor%20Or%C3%A7amentos/catalogoIA/.env) na raiz do projeto e preencha as variáveis:

*   **`GEMINI_API_KEY`**: Sua chave de API obtida gratuitamente no [Google AI Studio](https://aistudio.google.com/).
*   **`SUPABASE_URL`**: A URL do seu projeto no Supabase (pode ser encontrada em *Project Settings > API > Project URL*).
*   **`SUPABASE_KEY`**: A chave pública do Supabase (encontrada em *Project Settings > API > `anon` `public` key*).
*   **`SUPABASE_SERVICE_ROLE_KEY`**: A chave de serviço de administração do Supabase (encontrada em *Project Settings > API > `service_role` key*). **Atenção:** Esta chave tem permissões de escrita e é necessária para rodar o script de inserção.

---

## 3. Rodar a Ingestão dos Catálogos

Com a pasta de catálogos pronta (padrão: `C:\Users\Tecnologia\OneDrive - GRUPO RETEC\Documentos\CATALOGOS 2026`), você pode iniciar o processamento de leitura, OCR e upload vetorial:

1. Abra o terminal (PowerShell ou Command Prompt).
2. Vá para a pasta do projeto:
    ```powershell
    cd "C:\Users\Tecnologia\Agente - Setor Orçamentos\catalogoIA"
    ```
3. Execute o script de inserção:
    ```powershell
    .\.venv\Scripts\python inserir\inserir.py
    ```

*O script indexará automaticamente os PDFs. Arquivos já indexados serão ignorados caso o script seja interrompido e executado novamente.*

---

## 4. Iniciar o Chatbot (Interface Streamlit)

Após ter pelo menos alguns catálogos indexados no Supabase, você pode subir a interface web do chat:

1. No terminal, execute:
    ```powershell
    .\.venv\Scripts\streamlit run app\app.py
    ```
2. O navegador abrirá automaticamente no endereço `http://localhost:8501`.
3. Pronto! Você e a equipe de orçamentos já podem interagir com o agente.
