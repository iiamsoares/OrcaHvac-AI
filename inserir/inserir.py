import os
import sys
import time
import fitz  # PyMuPDF
import google.generativeai as genai
from supabase import create_client, Client
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer

# Importar o leitor que desenvolvemos
from leitor import extrair_texto_da_pagina

# Inicializar o modelo de embeddings local
print("Carregando o modelo 'intfloat/multilingual-e5-base' na CPU...")
modelo_e5 = SentenceTransformer('intfloat/multilingual-e5-base')
print("Modelo de embeddings locais carregado com sucesso!")

# Carregar variáveis de ambiente
load_dotenv()

# Configurar APIs
api_key = os.getenv("GEMINI_API_KEY")
if api_key:
    genai.configure(api_key=api_key)

supabase_url = os.getenv("SUPABASE_URL")
supabase_service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

if not supabase_url or not supabase_service_key:
    print("AVISO: SUPABASE_URL ou SUPABASE_SERVICE_ROLE_KEY não configurados no arquivo .env!")

# Inicializar cliente do Supabase
supabase: Client = None
if supabase_url and supabase_service_key:
    supabase = create_client(supabase_url, supabase_service_key)

def obter_embedding(texto):
    """
    Gera o vetor de embeddings local usando o modelo multilingual-e5-base na CPU.
    Para passagens/documentos, o modelo exige o prefixo "passage: ".
    """
    try:
        # E5 exige prefixo "passage: " para os textos que serão gravados no banco
        texto_formatado = f"passage: {texto}"
        embedding = modelo_e5.encode(texto_formatado, normalize_embeddings=True)
        # Converter de numpy array para lista Python
        return embedding.tolist()
    except Exception as e:
        print(f"  [ERRO] Falha ao gerar embedding local: {str(e)}")
        return None

def obter_paginas_indexadas(caminho_arquivo):
    """
    Retorna o conjunto de páginas já indexadas no Supabase para o arquivo com base no seu caminho relativo.
    """
    if not supabase:
        return set()
    try:
        resposta = supabase.table("documentos_catalogos_local").select("pagina").eq("caminho_arquivo", caminho_arquivo).execute()
        return set([d['pagina'] for d in resposta.data]) if resposta.data else set()
    except Exception as e:
        print(f"Erro ao verificar páginas indexadas no Supabase: {str(e)}")
        return set()

def indexar_catalogo(caminho_pdf, diretorio_base):
    """
    Lê o PDF página por página, gera embeddings e salva no Supabase.
    """
    nome_arquivo = os.path.basename(caminho_pdf)
    caminho_relativo = os.path.relpath(caminho_pdf, diretorio_base)
    
    try:
        doc = fitz.open(caminho_pdf)
        total_paginas = len(doc)
        doc.close()
        
        # Verificar quais páginas já estão indexadas pelo caminho relativo
        paginas_indexadas = obter_paginas_indexadas(caminho_relativo)
        
        if len(paginas_indexadas) == total_paginas:
            print(f"-> Arquivo 100% indexado anteriormente (Ignorando): {caminho_relativo}")
            return
            
        if paginas_indexadas:
            print(f"\nRetomando indexação parcial do arquivo: {caminho_relativo} ({len(paginas_indexadas)}/{total_paginas} páginas já indexadas)")
        else:
            print(f"\nIniciando indexação do arquivo: {caminho_relativo}")
        
        registros = []
        
        for i in range(total_paginas):
            pagina_humana = i + 1
            
            # Se esta página específica já foi indexada, pular
            if pagina_humana in paginas_indexadas:
                continue
                
            # Determinar a marca automaticamente com base no caminho absoluto do arquivo
            marca = "Outra"
            if "ARMACELL" in caminho_pdf.upper():
                marca = "Armacell"
            elif "DAIKIN" in caminho_pdf.upper():
                marca = "Daikin"
            elif "TROX" in caminho_pdf.upper():
                marca = "Trox"
                
            # Habilitar OCR para todos os que necessitarem dele (incluindo Daikin e Trox)
            permitir_ocr = True
            
            # Extrair texto (nativo ou OCR)
            texto_pagina, ocr_realizado = extrair_texto_da_pagina(caminho_pdf, i, permitir_ocr=permitir_ocr)
            
            if texto_pagina is not None:
                # Remover caracteres NULL (\u0000) para evitar erro no banco PostgreSQL
                texto_pagina = texto_pagina.replace("\x00", "").replace("\u0000", "")
            
            if texto_pagina is None:
                # Erro de API/OCR (como cota esgotada 429). Abortamos para não deixar lacunas!
                print(f"  [ERRO CRÍTICO] Falha ao processar a página {pagina_humana} de {nome_arquivo}. Abortando execução para evitar páginas em branco.")
                raise RuntimeError(f"Falha de API na página {pagina_humana}. Limite de requisições excedido ou falha de rede.")
            
            if len(texto_pagina.strip()) < 10:
                print(f"  Página {pagina_humana} de {nome_arquivo} está vazia ou sem conteúdo útil. Pulando...")
                continue
            
            # Gerar embedding da página
            embedding = obter_embedding(texto_pagina)
            
            # Pequeno intervalo se rodou OCR para respeitar o limite da API Gemini gratuita
            if ocr_realizado:
                time.sleep(5.0)
            else:
                time.sleep(0.01)
            
            if not embedding:
                print(f"  [ERRO CRÍTICO] Falha ao gerar embedding para a página {pagina_humana}. Abortando.")
                raise RuntimeError(f"Falha ao gerar embedding na página {pagina_humana}.")

            # Montar registro para inserção
            registro = {
                "nome_arquivo": nome_arquivo,
                "caminho_arquivo": caminho_relativo,
                "pagina": pagina_humana,
                "conteudo": texto_pagina,
                "embedding": embedding,
                "marca": marca
            }
            registros.append(registro)
            
            # Salvar no Supabase a cada 5 registros ou no final
            if len(registros) >= 5 or i == total_paginas - 1:
                if supabase and registros:
                    try:
                        supabase.table("documentos_catalogos_local").insert(registros).execute()
                        print(f"  [Progresso] {len(registros)} páginas salvas com sucesso no Supabase.")
                        registros = []
                    except Exception as db_err:
                        print(f"  [ERRO DB] Falha ao salvar lote no Supabase: {str(db_err)}")
                        raise db_err
                        
        # Salvar qualquer registro pendente que sobrou
        if supabase and registros:
            supabase.table("documentos_catalogos_local").insert(registros).execute()
            print(f"  [Progresso] {len(registros)} páginas salvas com sucesso no Supabase.")
            
        print(f"Concluída indexação de: {nome_arquivo}")
        
    except Exception as e:
        print(f"Erro ao processar o arquivo {caminho_pdf}: {str(e)}")
        # Propagar erro crítico para parar o loop geral de arquivos
        if isinstance(e, RuntimeError):
            raise e

def processar_pasta(diretorio_origem):
    """
    Percorre a pasta de catálogos e inicia a ingestão.
    """
    if not os.path.exists(diretorio_origem):
        print(f"Erro: O diretório de origem '{diretorio_origem}' não existe.")
        return
        
    print(f"Varrendo a pasta de catálogos: {diretorio_origem}")
    
    try:
        for raiz, pastas, arquivos in os.walk(diretorio_origem):
            for arquivo in arquivos:
                if arquivo.lower().endswith('.pdf'):
                    caminho_completo = os.path.join(raiz, arquivo)
                    indexar_catalogo(caminho_completo, diretorio_origem)
    except RuntimeError as e:
        print(f"\n[EXECUÇÃO INTERROMPIDA] O script foi parado devido a um erro crítico: {str(e)}")
        print("Você pode rodar o script novamente mais tarde para continuar de onde parou.")

if __name__ == "__main__":
    caminho_padrao = r"C:\Users\Tecnologia\OneDrive - GRUPO RETEC\Documentos\CATALOGOS 2026"
    if len(sys.argv) > 1:
        caminho_padrao = sys.argv[1]
        
    if not supabase:
        print("Erro: Supabase não está configurado. Configure o .env e tente novamente.")
        sys.exit(1)
        
    processar_pasta(caminho_padrao)
