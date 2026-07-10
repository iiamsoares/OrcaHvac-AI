import os
import json
import fitz  # PyMuPDF

def scan_local_catalogs(base_dir):
    brands_mapping = {
        "EQUIPAMENTOS ARMACELL": ("Armacell", "EQUIPAMENTOS ARMACELL"),
        "EQUIPAMENTOS DAIKIN": ("Daikin", "EQUIPAMENTOS DAIKIN"),
        "EQUIPAMENTOS TROX": ("Trox", "EQUIPAMENTOS TROX")
    }
    
    arquivos_locais = []
    
    for folder_name, (marca, subdir) in brands_mapping.items():
        subdir_path = os.path.join(base_dir, folder_name)
        if not os.path.exists(subdir_path):
            print(f"[Aviso] Pasta não encontrada: {subdir_path}")
            continue
            
        print(f"Varrendo pasta local da marca {marca}...")
        for root, _, files in os.walk(subdir_path):
            for file in files:
                if file.lower().endswith('.pdf'):
                    caminho_completo = os.path.join(root, file)
                    caminho_relativo = os.path.relpath(caminho_completo, subdir_path)
                    
                    try:
                        doc = fitz.open(caminho_completo)
                        total_paginas = len(doc)
                        doc.close()
                        
                        arquivos_locais.append({
                            "caminho_arquivo": caminho_relativo,
                            "nome_arquivo": file,
                            "marca": marca,
                            "total_paginas": total_paginas
                        })
                    except Exception as e:
                        print(f"  [Erro] Falha ao abrir {file}: {str(e)}")
                        
    return arquivos_locais

def main():
    base_dir = r"C:\Users\Tecnologia\OneDrive - GRUPO RETEC\Documentos\CATALOGOS 2026"
    output_path = r"c:\Users\Tecnologia\Agente - Setor Orçamentos\catalogoIA\dashboard\public\dados_locais.json"
    
    print(f"Iniciando varredura em: {base_dir}")
    dados = scan_local_catalogs(base_dir)
    
    # Garantir que a pasta de destino exista
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)
        
    print(f"\nSucesso! {len(dados)} arquivos locais indexados no JSON em: {output_path}")

if __name__ == "__main__":
    main()
