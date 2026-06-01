import os
import google.generativeai as genai
from supabase import create_client, Client
from dotenv import load_dotenv

# Carregar variáveis de ambiente inicialmente
load_dotenv()

# Inicializadores globais e cache de chaves para suportar hot-reload do .env
_api_key_inicializada = None
_supabase_url_inicializado = None
_supabase_key_inicializado = None
supabase: Client = None

# Modelo de embeddings local lazy initialized
modelo_e5 = None

def obter_modelo_embeddings():
    global modelo_e5
    if modelo_e5 is None:
        from sentence_transformers import SentenceTransformer
        print("Carregando o modelo 'intfloat/multilingual-e5-base' na CPU...")
        modelo_e5 = SentenceTransformer('intfloat/multilingual-e5-base')
        print("Modelo de embeddings locais carregado com sucesso!")
    return modelo_e5

def configurar_gemini():
    global _api_key_inicializada
    load_dotenv(override=True)
    key = os.getenv("GEMINI_API_KEY")
    if key and key != _api_key_inicializada:
        try:
            genai.configure(api_key=key)
            _api_key_inicializada = key
        except Exception as e:
            print(f"Erro ao configurar Gemini: {str(e)}")
    return key

def obter_cliente_supabase():
    global supabase, _supabase_url_inicializado, _supabase_key_inicializado
    load_dotenv(override=True)
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_KEY")
    
    if not supabase or url != _supabase_url_inicializado or key != _supabase_key_inicializado:
        if url and key:
            try:
                supabase = create_client(url, key)
                _supabase_url_inicializado = url
                _supabase_key_inicializado = key
            except Exception as e:
                print(f"Erro ao criar cliente Supabase: {str(e)}")
                supabase = None
        else:
            supabase = None
    return supabase

def obter_embedding_pergunta(texto):
    """
    Gera o vetor de embeddings para a pergunta do usuário usando o modelo local E5.
    Para queries, o modelo exige o prefixo "query: ".
    """
    try:
        model = obter_modelo_embeddings()
        texto_formatado = f"query: {texto}"
        embedding = model.encode(texto_formatado, normalize_embeddings=True)
        return embedding.tolist()
    except Exception as e:
        print(f"Erro ao gerar embedding da pergunta: {str(e)}")
        return None

def buscar_contexto(pergunta, limite=5, score_minimo=0.4, filtro_marcas=None):
    """
    Transforma a pergunta em embedding e pesquisa no Supabase trechos semelhantes.
    Retorna None em caso de falha de API, permitindo tratamento diferenciado.
    """
    client = obter_cliente_supabase()
    if not client:
        print("Erro: Supabase não inicializado.")
        return None
        
    embedding_pergunta = obter_embedding_pergunta(pergunta)
    if not embedding_pergunta:
        # Retorna None para sinalizar falha na API de embedding (como cota esgotada)
        return None
        
    try:
        # Chamar a função RPC 'buscar_documentos' criada no Supabase
        parametros = {
            "query_embedding": embedding_pergunta,
            "match_threshold": score_minimo,
            "match_count": limite
        }
        
        # Adicionar o filtro se o usuário escolheu marcas específicas
        if filtro_marcas:
            parametros["filtro_marcas"] = filtro_marcas
            
        resposta = client.rpc("buscar_documentos_local", parametros).execute()
        return resposta.data
    except Exception as e:
        print(f"Erro ao buscar no Supabase via RPC: {str(e)}")
        return []

def obter_catalogo_meta():
    """
    Busca no Supabase todos os catálogos únicos indexados por marca.
    Usa paginação para contornar o limite padrão de 1000 registros do Supabase.
    """
    client = obter_cliente_supabase()
    if not client:
        return ""
    try:
        todas_linhas = []
        limit = 1000
        offset = 0
        while True:
            res = client.table("documentos_catalogos_local")\
                .select("marca, nome_arquivo")\
                .range(offset, offset + limit - 1)\
                .execute()
            if not res.data:
                break
            todas_linhas.extend(res.data)
            if len(res.data) < limit:
                break
            offset += limit
            
        catalogos_por_marca = {}
        for r in todas_linhas:
            marca = r.get("marca") or "Outra"
            nome_arq = r.get("nome_arquivo") or "Desconhecido"
            if marca not in catalogos_por_marca:
                catalogos_por_marca[marca] = set()
            catalogos_por_marca[marca].add(nome_arq)
            
        linhas_meta = []
        for marca, arqs in sorted(catalogos_por_marca.items()):
            linhas_meta.append(f"Marca {marca}:")
            for arq in sorted(arqs):
                linhas_meta.append(f"  - {arq}")
        return "\n".join(linhas_meta)
    except Exception as e:
        print(f"Erro ao obter metadados dos catálogos: {str(e)}")
        return ""

def responder_pergunta(pergunta, limite_fontes=5, filtro_marcas=None):
    """
    Orquestra o RAG: busca o contexto relevante e usa o Gemini Pro para formular a resposta.
    """
    api_key = configurar_gemini()
    if not api_key:
        return "Erro: GEMINI_API_KEY não configurada no arquivo .env. Configure para usar o agente.", []

    # Detectar se o usuário está fazendo perguntas sobre o acervo/metadados
    perguntas_metadados = ["quais catalogos", "quais marcas", "qual catalogo", "listar catalogos", "lista de catalogos", "documentos disponiveis", "quais arquivos", "o que tem no banco", "quais documentos", "qual arquivo"]
    eh_meta = any(p in pergunta.lower() for p in perguntas_metadados)
    
    contexto_meta = ""
    if eh_meta:
        contexto_meta = obter_catalogo_meta()

    # 1. Buscar trechos semelhantes no banco de dados vetorial
    trechos = buscar_contexto(pergunta, limite=limite_fontes, filtro_marcas=filtro_marcas)
    
    if trechos is None:
        # Falha de API (como cota diária de embeddings esgotada)
        if eh_meta and contexto_meta:
            # Se for uma pergunta de metadados, podemos responder mesmo sem busca semântica!
            trechos = []
            contexto_formatado = "Aviso: Busca semântica indisponível devido a limite de cota de API atingido."
            fontes = []
        else:
            return (
                "Desculpe, ocorreu um erro temporário no processamento técnico. "
                "O limite diário de requisições gratuitas (cota da API Gemini) foi excedido no servidor. "
                "Por conta disso, não foi possível converter a pergunta para realizar a busca semântica nos catálogos. "
                "Por favor, aguarde o reset da cota diária ou insira uma chave de API ativa.",
                []
            )
    elif not trechos:
        contexto_formatado = "Nenhum documento relevante encontrado nas bases de dados para esta pergunta."
        fontes = []
    else:
        # Formatar o contexto que será injetado no prompt
        blocos_contexto = []
        fontes = []
        
        for t in trechos:
            nome_arq = t.get("nome_arquivo", "Desconhecido")
            caminho_arq = t.get("caminho_arquivo", "")
            pag = t.get("pagina", 0)
            conteudo = t.get("conteudo", "")
            similaridade = t.get("similarity", 0)
            marca = t.get("marca", "Desconhecida")
            
            blocos_contexto.append(
                f"--- FONTE: {nome_arq} (Página {pag} - Marca {marca}) ---\n"
                f"{conteudo}\n"
            )
            
            fontes.append({
                "nome": nome_arq,
                "caminho": caminho_arq,
                "pagina": pag,
                "marca": marca,
                "score": similaridade
            })
            
        contexto_formatado = "\n".join(blocos_contexto)
        
    # 2. Construir o Prompt de Sistema com as fontes
    meta_secao = ""
    if contexto_meta:
        meta_secao = f"--- CATÁLOGOS CADASTRADOS NO BANCO DE DADOS ---\n{contexto_meta}\n\n"

    prompt_sistema = (
        "Você é o 'catalogoIA', um agente assistente técnico especializado no setor de orçamentos de HVAC (Climatização, Ventilação e Aquecimento) da empresa.\n"
        "Sua principal função é ler os trechos de catálogos fornecidos como contexto e responder à pergunta do usuário de forma altamente profissional, técnica e precisa.\n\n"
        "Regras fundamentais:\n"
        "1. Use APENAS as informações presentes no contexto fornecido abaixo para responder à pergunta. Não invente dados técnicos.\n"
        "2. Se as fontes fornecidas não contiverem as informações necessárias para responder, diga honestamente que não encontrou essa informação nos catálogos disponíveis atualmente.\n"
        "3. Sempre que der um dado técnico (como vazão, perda de carga, ruído ou dimensões), cite no final do parágrafo de qual catálogo e página você obteve a informação (exemplo: [Catálogo Grelhas AT, Pág. 3]).\n"
        "4. Formate sua resposta de forma limpa, utilizando bullet points e tabelas em Markdown quando apropriado para facilitar a leitura por parte do orçamentista.\n"
        "5. Seja conciso e direto ao ponto.\n\n"
        f"{meta_secao}"
        f"--- CONTEXTO DE TRECHOS SELECIONADOS ---\n{contexto_formatado}\n"
    )
    
    # 3. Chamar o modelo do Gemini Pro
    try:
        # Tenta usar o Gemini Pro como cérebro principal para raciocínio complexo
        modelo = genai.GenerativeModel("gemini-pro-latest")
        resposta = modelo.generate_content([prompt_sistema, f"Pergunta do Usuário: {pergunta}"])
        return resposta.text, fontes
    except Exception as e:
        print(f"Erro com Gemini Pro: {str(e)}. Tentando fallback com Gemini Flash Lite...")
        try:
            # Fallback para o Gemini Flash Lite se o Pro falhar ou não estiver disponível
            modelo = genai.GenerativeModel("gemini-3.1-flash-lite")
            resposta = modelo.generate_content([prompt_sistema, f"Pergunta do Usuário: {pergunta}"])
            return resposta.text, fontes
        except Exception as e2:
            return f"Erro ao processar resposta via IA: {str(e2)}", fontes

if __name__ == "__main__":
    # Teste rápido de consulta
    import sys
    if len(sys.argv) > 1:
        q = sys.argv[1]
        print(f"Buscando resposta para: {q}")
        resposta, fontes = responder_pergunta(q)
        print("\n=== RESPOSTA ===")
        print(resposta)
        print("\n=== FONTES UTILIZADAS ===")
        for f in fontes:
            print(f"- {f['nome']} (Pág. {f['pagina']}) - Score: {f['score']:.4f}")
    else:
        print("Para testar, execute: python agente.py <pergunta_do_usuario>")
