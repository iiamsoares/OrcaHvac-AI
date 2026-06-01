-- Habilitar a extensão pgvector para trabalhar com busca semântica (vetorial)
create extension if not exists vector;

-- Criar a tabela para armazenar os trechos de texto dos catálogos
create table if not exists documentos_catalogos (
  id uuid primary key default gen_random_uuid(),
  nome_arquivo text not null,
  caminho_arquivo text not null,
  pagina integer not null,
  conteudo text not null,
  marca text, -- Marca correspondente (Trox, Daikin, Armacell)
  embedding vector(768), -- O modelo gemini-embedding-001 gera vetores de 768 dimensões
  criado_em timestamp with time zone default timezone('utc'::text, now()) not null
);

-- Habilitar RLS (Row Level Security) - opcional, mas seguro
alter table documentos_catalogos enable row level security;

-- Criar uma política de acesso público de leitura para simplificar consultas
create policy "Acesso público de leitura"
  on documentos_catalogos for select
  using (true);

-- Criar uma política de escrita para a chave service role (inserção de dados)
create policy "Acesso de escrita para service role"
  on documentos_catalogos for insert
  with check (true);

-- Criar a função RPC no Postgres para realizar busca por similaridade de cosseno com suporte a filtro de marcas
create or replace function buscar_documentos (
  query_embedding vector(768),
  match_threshold float,
  match_count int,
  filtro_marcas text[] default null
)
returns table (
  id uuid,
  nome_arquivo text,
  caminho_arquivo text,
  pagina int,
  conteudo text,
  marca text,
  similarity float
)
language plpgsql stable
as $$
begin
  return query
  select
    dc.id,
    dc.nome_arquivo,
    dc.caminho_arquivo,
    dc.pagina,
    dc.conteudo,
    dc.marca,
    1 - (dc.embedding <=> query_embedding) as similarity
  from documentos_catalogos dc
  where 1 - (dc.embedding <=> query_embedding) > match_threshold
    and (filtro_marcas is null or dc.marca = any(filtro_marcas))
  order by dc.embedding <=> query_embedding
  limit match_count;
end;
$$;

-- Criar um índice para otimizar as buscas por similaridade de cosseno (opcional, para acelerar buscas com pgvector)
create index if not exists documentos_catalogos_embedding_idx 
  on documentos_catalogos 
  using hnsw (embedding vector_cosine_ops);
