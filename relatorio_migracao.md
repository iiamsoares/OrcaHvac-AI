# Relatório de Migração e Consolidação - catalogoIA
**Data:** 29 de Maio de 2026  
**Setor:** Departamento de Orçamentos - HVAC  

---

## 1. Contexto e Motivação
Anteriormente, o sistema utilizava a API de Embeddings do Gemini (`gemini-embedding-001`) para vetorizar as páginas de catálogos e realizar buscas. Devido aos limites rígidos de cota gratuita (erros `429 / Quota Exceeded`), o processo de indexação de mais de 2.000 páginas era constantemente interrompido. 

A solução proposta e implementada foi a **migração para um modelo de embeddings 100% local e gratuito**, rodando na CPU da máquina do usuário.

---

## 2. O que foi feito (Entregas Realizadas)

### A. Teste de Validação e Escolha do Modelo
Desenvolvemos e rodamos o script `teste_local.py` utilizando o modelo **`intfloat/multilingual-e5-base`** (dimensão 768) na CPU local. O teste avaliou perguntas técnicas reais em português e obteve **100% de acerto** (relevância máxima no 1º resultado):
*   *Canos suando* $\rightarrow$ Isolamento ArmaFlex (85.01%)
*   *Abafar barulho nos dutos* $\rightarrow$ Atenuadores TROX (84.56%)
*   *Direcionar o ar na sala* $\rightarrow$ Grelha de insuflação (83.69%)
*   *Chiller com scroll* $\rightarrow$ Chiller BC-SC (86.49%)

### B. Nova Arquitetura do Banco de Dados (Supabase)
Em vez de apagar os dados antigos, criamos uma estrutura paralela e independente para os embeddings locais:
*   **Nova Tabela:** `documentos_catalogos_local` com vetorização de 768 dimensões.
*   **Nova Função RPC:** `buscar_documentos_local` para realizar buscas por cosseno isoladas nesta tabela.
*   **Índice HNSW:** Habilitado para otimizar a velocidade de busca.

### C. Atualização dos Códigos do Projeto
*   `inserir.py`:
    *   Integrado com a biblioteca `sentence-transformers` para carregar o modelo local na inicialização.
    *   Adicionado o prefixo obrigatório `"passage: "` para otimização de busca do modelo E5.
    *   **Otimização de Performance:** Removemos o intervalo de pausa (`time.sleep`) para PDFs nativos que não necessitam de OCR, tornando o upload **mais de 10 vezes mais rápido** (indexação de 2.500+ páginas concluída em menos de 40 minutos).
    *   **Correção de Bug (Marca):** Corrigido o seletor automático de marcas para verificar o caminho absoluto do arquivo (`caminho_pdf`), garantindo que os uploads sejam classificados corretamente como `Armacell` ou `Daikin`, evitando o fallback genérico `"Outra"`.
*   `agente.py`:
    *   Adicionado o carregamento em cache (lazy loading) do modelo local.
    *   Atualizada a função `obter_embedding_pergunta` para adicionar o prefixo `"query: "` e usar a CPU local.
    *   Redirecionada a busca semântica para a nova RPC `buscar_documentos_local` e a tabela `documentos_catalogos_local`.
*   `app.py`:
    *   Atualizado o painel lateral de estatísticas para consultar a tabela `documentos_catalogos_local`.
*   `requirements.txt`:
    *   Adicionada a biblioteca `sentence-transformers`.

---

## 3. Status Atual da Indexação (29/05/2026)

Concluímos a indexação piloto e de produção em segundo plano. O estado atual da nova base vetorial é:

*   **Total de páginas indexadas no banco:** **2.617 páginas**
*   **Armacell:** **105 páginas** (34 manuais/arquivos, 100% concluído).
*   **Daikin:** **2.512 páginas** (61 manuais/arquivos, 100% dos PDFs nativos concluído).

---

## 4. O que ficou faltando (Pendências)

### A. Catálogos da Daikin que exigem OCR (11 arquivos)
Dos 136 arquivos presentes no disco da Daikin, **11 arquivos únicos** não possuem texto selecionável (são apenas imagens digitalizadas). Como a marca estava configurada para pular o OCR nesta rodada para poupar cota, eles foram ignorados e não constam no banco.

Estes arquivos estão nas seguintes pastas:
1.  `Multi Split Lite Smart R-32\Manual de Instalação` (INS_indoor_CTXC09-12RMVM.pdf, INS_outdoor_2MXC18RMVM.pdf)
2.  `Multi Split Lite Smart R-32\Manual de Operação` (OPE_Multi-Split-Lite-Smart-R-32_2MXC-R.pdf)
3.  `Reiri\Catálogo` (202509 FBRVPRFOV03D0925 Folheto Reiri.pdf)
4.  `Split EcoSwing Smart Gold R-32\Manual de Instalação` (3P611134-1D Manual de Instalação...)
5.  `Split EcoSwing Smart R-32\Manual de Instalação` (INS-FTHP_Q5VL - EcoSwing Smart...)
6.  `Split Hi Wall Full Inverter\Manual de Operação` (202526 Manual de Operação.pdf)
7.  `VRV FIT-Unidades Externas\Manual de Instalação` (dois manuais do FIT)
8.  `VRV INOVA-Unidades Externas\Manual de Instalação` (dois manuais do INOVA)

*Nota: Os outros 64 arquivos do disco da Daikin são apenas cópias repetidas desses mesmos manuais.*

### B. Catálogos da TROX
A indexação da pasta da TROX foi ignorada nesta rodada por solicitação inicial (foco em Armacell e Daikin). Ela exige processamento de OCR completo via Gemini.

---

## 5. Próximos Passos Recomendados

### Passo 1: Validar o Chatbot Streamlit
Abra seu navegador no endereço `http://localhost:8501`. As estatísticas do painel lateral deverão mostrar as **2.617 páginas** e você já poderá fazer qualquer consulta técnica complexa sobre os catálogos da Armacell e da Daikin.

### Passo 2: Indexar os 11 arquivos da Daikin com OCR (Opcional)
Caso precise que a IA busque nesses manuais específicos que são imagem, podemos rodar uma carga direcionada ativando o OCR no arquivo de inserção para processar apenas essa lista de 11 arquivos.

### Passo 3: Indexar a TROX
Quando quiser iniciar a indexação da TROX, precisaremos remover o bloco de filtro `if "EQUIPAMENTOS TROX" in raiz: continue` do script `inserir.py`. Por exigir OCR em grande escala, recomenda-se acompanhar a cota de requisições da API.
