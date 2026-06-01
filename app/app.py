import streamlit as st
import os
import sys

# Garantir que a pasta 'app' e o diretório raiz estejam no path para importar o agente
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agente import responder_pergunta, obter_cliente_supabase

# Configuração da página Streamlit (Deve ser a primeira chamada da página)
st.set_page_config(
    page_title="Catálogo IA - Setor Orçamentos",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Estilização CSS personalizada para um design dark premium e de alta visibilidade
st.markdown("""
<style>
    /* Fundo escuro para a aplicação inteira */
    .main {
        background-color: #0f172a !important;
    }
    .stApp {
        background-color: #0f172a !important;
    }
    /* Títulos em branco de alto contraste */
    h1, h2, h3, h4, h5, h6 {
        color: #ffffff !important;
        font-family: 'Inter', sans-serif;
    }
    .sidebar .sidebar-content {
        background-color: #1e293b !important;
    }
    .stChatMessage {
        border-radius: 12px;
        padding: 15px;
        margin-bottom: 10px;
        box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1), 0 2px 4px -1px rgba(0,0,0,0.06);
    }
    /* Mensagem do Usuário: Fundo azul escuro e texto branco */
    .stChatMessage[data-testid="stChatMessageUser"] {
        background-color: #1e40af !important;
        border-left: 5px solid #3b82f6 !important;
    }
    .stChatMessage[data-testid="stChatMessageUser"] * {
        color: #ffffff !important;
    }
    /* Mensagem do Bot: Fundo cinza chumbo escuro e texto branco puro */
    .stChatMessage[data-testid="stChatMessageAssistant"] {
        background-color: #1e293b !important;
        border-left: 5px solid #10b981 !important;
    }
    .stChatMessage[data-testid="stChatMessageAssistant"] * {
        color: #ffffff !important;
    }
    /* Forçar cor azul claro brilhante para links nas respostas */
    .stChatMessage[data-testid="stChatMessageAssistant"] a {
        color: #38bdf8 !important;
        text-decoration: underline !important;
    }
    /* Cor branca para textos dos expansores (fontes consultadas) */
    .stExpander * {
        color: #ffffff !important;
    }
    .fonte-tag {
        display: inline-block;
        background-color: #334155;
        color: #f8fafc !important;
        padding: 2px 8px;
        border-radius: 4px;
        font-size: 0.8rem;
        margin-right: 5px;
        margin-bottom: 5px;
        border: 1px solid #475569;
    }
</style>
""", unsafe_allow_html=True)

# --- SIDEBAR / PAINEL LATERAL ---
with st.sidebar:
    st.image(r"C:\Users\Tecnologia\OneDrive - GRUPO RETEC (1)\02. Engenharia\Dep. Orçamentos\CADASTRO ORÇAMENTO RETEC\CORE\imagens\LOGO RETEC-Photoroom.png", width=100)
    st.title("Configurações")
    
    st.markdown("---")
    
    st.subheader("💡 Parâmetros de Busca")
    limite_fontes = st.slider("Máximo de páginas fontes (RAG)", min_value=1, max_value=10, value=5, step=1)
    
    st.markdown("---")
    
    st.subheader("🏷️ Filtrar por Marca")
    marcas_disponiveis = ["Armacell", "Daikin", "Trox"]
    marcas_selecionadas = st.multiselect("Pesquisar marcas:", marcas_disponiveis, default=marcas_disponiveis)
    
    st.markdown("---")
    
    # Exibir estatísticas do Supabase
    st.subheader("📊 Estatísticas do Sistema")
    supabase_client = obter_cliente_supabase()
    if supabase_client:
        try:
            # Buscar a quantidade de linhas no banco para exibir status
            resposta = supabase_client.table("documentos_catalogos_local").select("id", count="exact").execute()
            total_chunks = resposta.count if hasattr(resposta, "count") else len(resposta.data)
            
            # Buscar quantidade de catálogos únicos
            resposta_unicos = supabase_client.table("documentos_catalogos_local").select("nome_arquivo").execute()
            arquivos_unicos = len(set([doc['nome_arquivo'] for doc in resposta_unicos.data])) if resposta_unicos.data else 0
            
            st.metric("Páginas Indexadas", total_chunks)
            st.metric("Catálogos Cadastrados", arquivos_unicos)
            st.success("Banco de Dados Conectado")
        except Exception as e:
            st.error(f"Erro ao ler estatísticas do banco: {str(e)}")
    else:
        st.warning("Supabase não configurado ou desconectado. Verifique o arquivo .env.")

    st.markdown("---")
    st.info(
        "**Catálogo IA v1.0**\n\n"
        "Este agente pesquisa em tempo real os catálogos de produtos da TROX para responder dúvidas sobre especificações técnicas, vazões, materiais e códigos."
    )

# --- CONTEÚDO PRINCIPAL ---
st.title("🤖 Catálogo IA")
st.markdown("##### *Assistente Inteligente para Consulta de Catálogos Técnicos (Setor Orçamentos)*")

# Inicializar histórico de conversas no state se não existir
if "messages" not in st.session_state:
    st.session_state.messages = []

# Exibir histórico de mensagens
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        # Se for mensagem da IA e tiver fontes, exibe de forma discreta
        if message["role"] == "assistant" and "sources" in message and message["sources"]:
            with st.expander("🔍 Fontes originais consultadas para esta resposta:"):
                for idx, f in enumerate(message["sources"], 1):
                    st.markdown(
                        f"**{idx}.** {f['nome']} (Pág. {f['pagina']} - Marca: **{f.get('marca', 'Desconhecida')}**)  "
                        f"`Similaridade Semântica: {f['score']:.2%}`"
                    )

# Input do chat do usuário
if prompt := st.chat_input("Pergunte algo sobre os catálogos (ex: Qual a vazão da grelha AT?)"):
    # Adicionar mensagem do usuário ao histórico e exibir na tela
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Exibir spinner e processar resposta
    with st.chat_message("assistant"):
        resposta_placeholder = st.empty()
        
        # Determinar o filtro de marcas para o RAG
        filtro_marcas = marcas_selecionadas if len(marcas_selecionadas) < len(marcas_disponiveis) else None
        
        with st.spinner("Pesquisando nos catálogos e formulando resposta técnica..."):
            resposta, fontes = responder_pergunta(prompt, limite_fontes=limite_fontes, filtro_marcas=filtro_marcas)
            
            # Exibe a resposta
            resposta_placeholder.markdown(resposta)
            
            # Se houver fontes, exibe
            if fontes:
                with st.expander("🔍 Fontes originais consultadas para esta resposta:"):
                    for idx, f in enumerate(fontes, 1):
                        st.markdown(
                            f"**{idx}.** {f['nome']} (Pág. {f['pagina']} - Marca: **{f.get('marca', 'Desconhecida')}**)  "
                            f"`Similaridade Semântica: {f['score']:.2%}`"
                        )
                        
            # Adicionar a resposta da IA ao histórico de mensagens
            st.session_state.messages.append({
                "role": "assistant", 
                "content": resposta,
                "sources": fontes
            })
