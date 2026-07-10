import os
import io
# pyrefly: ignore [missing-import]
import fitz  # PyMuPDF
from PIL import Image
import google.generativeai as genai
from dotenv import load_dotenv

# Carregar variáveis de ambiente
load_dotenv()

# Configurar a chave da API do Gemini
api_key = os.getenv("GEMINI_API_KEY")
if api_key:
    genai.configure(api_key=api_key)

def extrair_texto_da_pagina(caminho_pdf, numero_pagina, forçar_ocr=False, permitir_ocr=True):
    """
    Extrai o texto de uma página de um PDF.
    Se o PDF for escaneado (sem texto selecionável) ou se forçar_ocr=True,
    utiliza o Gemini Multimodal para fazer o OCR e retornar tabelas em Markdown.
    """
    try:
        # Abrir o documento PDF
        doc = fitz.open(caminho_pdf)
        pagina = doc[numero_pagina]
        
        # 1. Tentar extrair o texto nativo primeiro
        texto_nativo = pagina.get_text()
        
        # Se contiver um texto razoável e não estivermos forçando o OCR, ou se OCR estiver desabilitado, retornamos
        if (texto_nativo and len(texto_nativo.strip()) > 100 and not forçar_ocr) or not permitir_ocr:
            print(f"[{os.path.basename(caminho_pdf)} - Pág. {numero_pagina + 1}] Texto nativo extraído (OCR desativado ou dispensável).")
            return (texto_nativo.strip() if texto_nativo else ""), False
        
        # 2. Se for imagem/escaneado, rodar OCR com o Gemini 1.5 Flash
        print(f"[{os.path.basename(caminho_pdf)} - Pág. {numero_pagina + 1}] Sem texto selecionável e permitir_ocr=True. Rodando OCR com Gemini...")
        
        if not api_key:
            raise ValueError("GEMINI_API_KEY não configurada no arquivo .env")
            
        # Renderizar a página do PDF como uma imagem em alta resolução (DPI=150)
        pix = pagina.get_pixmap(dpi=150)
        imagem_bytes = pix.tobytes("png")
        
        # Converter os bytes para objeto de Imagem PIL
        imagem = Image.open(io.BytesIO(imagem_bytes))
        
        # Configurar o modelo multimodal do Gemini Lite
        modelo = genai.GenerativeModel("gemini-3.1-flash-lite")
        
        prompt = (
            "Você é um leitor óptico e processador de documentos profissional. "
            "Sua tarefa é transcrever todo o texto presente nesta página de catálogo técnico de climatização/HVAC de forma fiel. "
            "Siga rigorosamente estas regras:\n"
            "1. Transcreva todos os textos informativos com exatidão.\n"
            "2. Transcreva TODAS as tabelas encontradas em formato Markdown (tabelas md). Mantenha cabeçalhos e valores perfeitamente alinhados.\n"
            "3. Se houver esquemas, figuras ou dados de engenharia, transcreva os textos e valores associados a eles.\n"
            "4. Mantenha os títulos de seções para manter a estrutura original da página.\n"
            "5. Não faça introduções, resumos ou explicações adicionais. Retorne apenas a transcrição do conteúdo da página."
        )
        
        # Chamar a API do Gemini enviando a imagem e o prompt com retentativa robusta para qualquer erro temporário (429, 500, rede, etc)
        tentativas = 5
        espera = 6
        resposta = None
        for tentativa in range(tentativas):
            try:
                resposta = modelo.generate_content([prompt, imagem])
                break
            except Exception as api_err:
                if tentativa == tentativas - 1:
                    # Se for a última tentativa, propaga o erro
                    raise api_err
                print(f"  [AVISO API] Erro na chamada (Tentativa {tentativa + 1}/{tentativas}): {str(api_err)}. Esperando {espera}s para tentar novamente...")
                import time
                time.sleep(espera)
                espera *= 2
        
        if not resposta:
            raise Exception("Falha após várias tentativas de chamada à API do Gemini devido a limites de cota.")
            
        try:
            texto_ocr = resposta.text
        except Exception as text_err:
            candidatos = getattr(resposta, "candidates", [])
            finish_reason = 0
            if candidatos:
                # O finish_reason pode ser int ou objeto com atributo value
                fr_obj = getattr(candidatos[0], "finish_reason", 0)
                if hasattr(fr_obj, "value"):
                    finish_reason = fr_obj.value
                else:
                    try:
                        finish_reason = int(fr_obj)
                    except:
                        finish_reason = 0
            
            # 3 = SAFETY, 4 = RECITATION
            if finish_reason == 4:
                print(f"  [AVISO OCR] Página {numero_pagina + 1} de {os.path.basename(caminho_pdf)} bloqueada por filtro de direitos autorais (RECITATION). Retornando placeholder.")
                return f"[Conteúdo da página {numero_pagina + 1} indisponível devido a restrição de direitos autorais no OCR do Gemini]", True
            elif finish_reason == 3:
                print(f"  [AVISO OCR] Página {numero_pagina + 1} de {os.path.basename(caminho_pdf)} bloqueada por filtro de segurança (SAFETY). Retornando placeholder.")
                return f"[Conteúdo da página {numero_pagina + 1} indisponível devido a filtro de segurança no OCR do Gemini]", True
            else:
                raise text_err
            
        if texto_ocr:
            print(f"[{os.path.basename(caminho_pdf)} - Pág. {numero_pagina + 1}] OCR concluído com sucesso.")
            return texto_ocr.strip(), True
        else:
            raise Exception("Retorno vazio da API do Gemini")
            
    except Exception as e:
        print(f"Erro ao extrair texto da página {numero_pagina + 1} de {caminho_pdf}: {str(e)}")
        return None, False
    finally:
        if 'doc' in locals():
            doc.close()

if __name__ == "__main__":
    # Teste rápido do leitor
    # Certifique-se de configurar a variável GEMINI_API_KEY no seu .env antes de rodar
    import sys
    if len(sys.argv) > 2:
        caminho = sys.argv[1]
        pag = int(sys.argv[2])
        texto, ocr = extrair_texto_da_pagina(caminho, pag)
        print("\n--- TEXTO EXTRAÍDO ---")
        print(texto)
        print(f"\nOCR realizado: {ocr}")
    else:
        print("Para testar, execute: python leitor.py <caminho_do_pdf> <numero_da_pagina_0_indexada>")
