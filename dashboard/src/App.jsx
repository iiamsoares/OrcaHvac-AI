import React, { useState, useEffect, useCallback, useRef } from 'react';
import { createClient } from '@supabase/supabase-js';
import { 
  RefreshCw, 
  Search, 
  CheckCircle, 
  Clock, 
  FileText, 
  Database, 
  AlertTriangle, 
  BarChart2,
  Filter,
  Check,
  Calendar,
  AlertCircle
} from 'lucide-react';

// Inicializar cliente do Supabase a partir das variáveis do Vite
const supabaseUrl = import.meta.env.VITE_SUPABASE_URL || '';
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY || '';

let supabase = null;
if (supabaseUrl && supabaseAnonKey) {
  supabase = createClient(supabaseUrl, supabaseAnonKey);
}

function App() {
  const [localFiles, setLocalFiles] = useState([]);
  const [dbPages, setDbPages] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [brandFilter, setBrandFilter] = useState('All');
  const [statusFilter, setStatusFilter] = useState('All');
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [lastUpdated, setLastUpdated] = useState(null);
  
  const autoRefreshTimerRef = useRef(null);

  // Função para carregar dados do Supabase e do arquivo JSON
  const fetchData = useCallback(async (silent = false) => {
    if (!supabase) {
      setError("Credenciais do Supabase não configuradas no .env. Por favor, execute o script 'python app/iniciar_painel.py' para configurar.");
      setLoading(false);
      return;
    }

    try {
      if (!silent) setLoading(true);
      
      // 1. Buscar JSON de arquivos locais
      const resLocal = await fetch('/dados_locais.json');
      if (!resLocal.ok) {
        throw new Error("Não foi possível carregar a lista de arquivos locais. Certifique-se de ter rodado o script de varredura.");
      }
      const localData = await resLocal.json();
      
      // 2. Buscar dados de páginas indexadas no Supabase
      // Buscamos apenas os campos necessários para otimizar a transferência de dados
      let allDbData = [];
      let limit = 1000;
      let offset = 0;
      
      while (true) {
        const { data, error: dbError } = await supabase
          .from('documentos_catalogos_local')
          .select('caminho_arquivo, pagina, marca')
          .range(offset, offset + limit - 1);
          
        if (dbError) throw dbError;
        if (!data || data.length === 0) break;
        
        allDbData = [...allDbData, ...data];
        if (data.length < limit) break;
        offset += limit;
      }
      
      setLocalFiles(localData);
      setDbPages(allDbData);
      setLastUpdated(new Date());
      setError(null);
    } catch (err) {
      console.error(err);
      setError(err.message || "Erro desconhecido ao carregar dados.");
    } finally {
      if (!silent) setLoading(false);
    }
  }, []);

  // Carregamento inicial
  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // Efeito para gerenciar o Auto-Refresh (a cada 5 segundos)
  useEffect(() => {
    if (autoRefresh) {
      autoRefreshTimerRef.current = setInterval(() => {
        fetchData(true);
      }, 5000);
    } else {
      if (autoRefreshTimerRef.current) {
        clearInterval(autoRefreshTimerRef.current);
      }
    }

    return () => {
      if (autoRefreshTimerRef.current) {
        clearInterval(autoRefreshTimerRef.current);
      }
    };
  }, [autoRefresh, fetchData]);

  // Processar e cruzar dados locais com dados do banco
  const processData = () => {
    // Agrupar páginas indexadas do Supabase por caminho relativo do arquivo
    const indexedPagesMap = {};
    dbPages.forEach(row => {
      const path = row.caminho_arquivo;
      if (!indexedPagesMap[path]) {
        indexedPagesMap[path] = new Set();
      }
      indexedPagesMap[path].add(row.pagina);
    });

    // Mapear arquivos locais adicionando o status e páginas indexadas
    const filesWithStatus = localFiles.map(file => {
      const pagesIndexedSet = indexedPagesMap[file.caminho_arquivo] || new Set();
      const pagesIndexedCount = pagesIndexedSet.size;
      
      let status = 'pending';
      if (pagesIndexedCount >= file.total_paginas) {
        status = 'completed';
      } else if (pagesIndexedCount > 0) {
        status = 'partial';
      }

      return {
        ...file,
        paginas_indexadas: pagesIndexedCount,
        status: status
      };
    });

    return filesWithStatus;
  };

  const processedFiles = processData();

  // Calcular estatísticas gerais
  const totalLocalFiles = processedFiles.length;
  const totalLocalPages = processedFiles.reduce((sum, f) => sum + f.total_paginas, 0);
  
  const completedFiles = processedFiles.filter(f => f.status === 'completed').length;
  const partialFiles = processedFiles.filter(f => f.status === 'partial').length;
  const pendingFiles = processedFiles.filter(f => f.status === 'pending').length;
  
  // Total de páginas indexadas reais (limitadas ao total do arquivo para evitar inconsistências)
  const totalIndexedPages = processedFiles.reduce((sum, f) => sum + Math.min(f.paginas_indexadas, f.total_paginas), 0);
  const overallProgress = totalLocalPages > 0 ? (totalIndexedPages / totalLocalPages) * 100 : 0;

  // Páginas pendentes de indexação no total
  const pendingOcrPages = totalLocalPages - totalIndexedPages;

  // Estatísticas por marca
  const brandsStats = ['Armacell', 'Daikin', 'Trox'].reduce((acc, brand) => {
    const brandFiles = processedFiles.filter(f => f.marca === brand);
    const brandTotalFiles = brandFiles.length;
    const brandTotalPages = brandFiles.reduce((sum, f) => sum + f.total_paginas, 0);
    const brandCompletedFiles = brandFiles.filter(f => f.status === 'completed').length;
    const brandIndexedPages = brandFiles.reduce((sum, f) => sum + Math.min(f.paginas_indexadas, f.total_paginas), 0);
    const brandProgress = brandTotalPages > 0 ? (brandIndexedPages / brandTotalPages) * 100 : 0;

    acc[brand] = {
      totalFiles: brandTotalFiles,
      totalPages: brandTotalPages,
      completedFiles: brandCompletedFiles,
      indexedPages: brandIndexedPages,
      progress: brandProgress
    };
    return acc;
  }, {});

  // Estimar tempo restante (com base no limite de 500 requisições diárias de OCR da API do Gemini gratuita)
  // Assumimos que páginas não indexadas em média ~70% precisam de OCR.
  const estimatedOcrPages = Math.round(pendingOcrPages * 0.73);
  const estimatedDays = Math.ceil(estimatedOcrPages / 500);

  // Filtrar arquivos de acordo com busca e seleções de filtros
  const filteredFiles = processedFiles.filter(file => {
    const matchesSearch = file.nome_arquivo.toLowerCase().includes(searchQuery.toLowerCase()) || 
                          file.caminho_arquivo.toLowerCase().includes(searchQuery.toLowerCase());
    
    const matchesBrand = brandFilter === 'All' || file.marca === brandFilter;
    
    const matchesStatus = statusFilter === 'All' || file.status === statusFilter;

    return matchesSearch && matchesBrand && matchesStatus;
  });

  return (
    <div className="app-container">
      {/* HEADER */}
      <header>
        <div className="logo-section">
          <h1>RETEC Catálogos</h1>
          <span>Painel de Ingestão IA</span>
        </div>
        
        <div className="actions-section">
          {lastUpdated && (
            <div className="live-indicator">
              <span className="pulse-dot"></span>
              <span>Alt. {lastUpdated.toLocaleTimeString()}</span>
            </div>
          )}
          
          <div className="toggle-container">
            <span>Auto-Refresh</span>
            <label className="toggle-switch">
              <input 
                type="checkbox" 
                checked={autoRefresh} 
                onChange={(e) => setAutoRefresh(e.target.checked)} 
              />
              <span className="slider"></span>
            </label>
          </div>
          
          <button className="btn-primary" onClick={fetchData} disabled={loading}>
            <RefreshCw size={16} className={loading ? "spin" : ""} />
            Atualizar Banco
          </button>
        </div>
      </header>

      {/* ERROR MESSAGE */}
      {error && (
        <div className="glass-card" style={{ borderColor: 'var(--color-pending)', background: 'rgba(239, 68, 68, 0.05)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.8rem', color: 'var(--color-pending)' }}>
            <AlertCircle size={24} />
            <h3 style={{ fontFamily: 'var(--font-title)', fontWeight: 600 }}>Falha na Conexão</h3>
          </div>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', lineHeight: '1.5' }}>{error}</p>
        </div>
      )}

      {/* METRICS GRID */}
      <div className="metrics-grid">
        {/* PROGRESSO GERAL */}
        <div className="glass-card">
          <div className="metric-header">
            <span>Progresso Geral</span>
            <BarChart2 size={16} />
          </div>
          <div className="metric-value">
            {overallProgress.toFixed(1)}%
          </div>
          <div className="progress-bar-container" style={{ margin: '0.5rem 0' }}>
            <div 
              className="progress-bar-fill" 
              style={{ 
                width: `${overallProgress}%`, 
                background: 'linear-gradient(90deg, var(--color-daikin) 0%, var(--color-trox) 100%)' 
              }}
            ></div>
          </div>
          <div className="metric-subtext">
            Total de páginas indexadas e integradas
          </div>
        </div>

        {/* ARQUIVOS INDEXADOS */}
        <div className="glass-card">
          <div className="metric-header">
            <span>Arquivos Concluídos</span>
            <FileText size={16} />
          </div>
          <div className="metric-value">
            {completedFiles} <span style={{ fontSize: '1rem', color: 'var(--text-secondary)' }}>/ {totalLocalFiles}</span>
          </div>
          <div className="metric-subtext" style={{ display: 'flex', gap: '0.5rem' }}>
            <span style={{ color: 'var(--color-completed)' }}>● {completedFiles} OK</span>
            <span style={{ color: 'var(--color-partial)' }}>● {partialFiles} Part.</span>
            <span style={{ color: 'var(--color-pending)' }}>● {pendingFiles} Pend.</span>
          </div>
        </div>

        {/* PÁGINAS NO BANCO */}
        <div className="glass-card">
          <div className="metric-header">
            <span>Páginas Ingeridas</span>
            <Database size={16} />
          </div>
          <div className="metric-value">
            {totalIndexedPages} <span style={{ fontSize: '1rem', color: 'var(--text-secondary)' }}>/ {totalLocalPages}</span>
          </div>
          <div className="metric-subtext">
            {pendingOcrPages} páginas pendentes no total
          </div>
        </div>

        {/* ESTIMATIVA RESTANTE */}
        <div className="glass-card">
          <div className="metric-header">
            <span>Cota e Conclusão</span>
            <Calendar size={16} />
          </div>
          <div className="metric-value">
            ~{estimatedDays} <span style={{ fontSize: '1rem', color: 'var(--text-secondary)' }}>dias</span>
          </div>
          <div className="metric-subtext">
            {estimatedOcrPages} págs. estimadas com OCR restante
          </div>
        </div>
      </div>

      {/* MARCAS GRID */}
      <div className="brands-section">
        {/* ARMACELL */}
        <div className="glass-card brand-card armacell">
          <div className="brand-header">
            <div className="brand-icon-wrapper">
              <Check size={18} />
            </div>
            <span className="brand-title">Armacell</span>
          </div>
          <div className="brand-stats-row">
            <div className="brand-stat-item">
              <span className="brand-stat-label">Arquivos</span>
              <span className="brand-stat-value">{brandsStats['Armacell']?.completedFiles || 0} / {brandsStats['Armacell']?.totalFiles || 0}</span>
            </div>
            <div className="brand-stat-item">
              <span className="brand-stat-label">Páginas</span>
              <span className="brand-stat-value">{brandsStats['Armacell']?.indexedPages || 0} / {brandsStats['Armacell']?.totalPages || 0}</span>
            </div>
          </div>
          <div className="progress-bar-container">
            <div className="progress-bar-fill" style={{ width: `${brandsStats['Armacell']?.progress || 0}%` }}></div>
          </div>
          <div className="metric-subtext" style={{ textAlign: 'right', fontWeight: '600' }}>
            {(brandsStats['Armacell']?.progress || 0).toFixed(1)}%
          </div>
        </div>

        {/* DAIKIN */}
        <div className="glass-card brand-card daikin">
          <div className="brand-header">
            <div className="brand-icon-wrapper">
              <Check size={18} />
            </div>
            <span className="brand-title">Daikin</span>
          </div>
          <div className="brand-stats-row">
            <div className="brand-stat-item">
              <span className="brand-stat-label">Arquivos</span>
              <span className="brand-stat-value">{brandsStats['Daikin']?.completedFiles || 0} / {brandsStats['Daikin']?.totalFiles || 0}</span>
            </div>
            <div className="brand-stat-item">
              <span className="brand-stat-label">Páginas</span>
              <span className="brand-stat-value">{brandsStats['Daikin']?.indexedPages || 0} / {brandsStats['Daikin']?.totalPages || 0}</span>
            </div>
          </div>
          <div className="progress-bar-container">
            <div className="progress-bar-fill" style={{ width: `${brandsStats['Daikin']?.progress || 0}%` }}></div>
          </div>
          <div className="metric-subtext" style={{ textAlign: 'right', fontWeight: '600' }}>
            {(brandsStats['Daikin']?.progress || 0).toFixed(1)}%
          </div>
        </div>

        {/* TROX */}
        <div className="glass-card brand-card trox">
          <div className="brand-header">
            <div className="brand-icon-wrapper">
              <Check size={18} />
            </div>
            <span className="brand-title">Trox</span>
          </div>
          <div className="brand-stats-row">
            <div className="brand-stat-item">
              <span className="brand-stat-label">Arquivos</span>
              <span className="brand-stat-value">{brandsStats['Trox']?.completedFiles || 0} / {brandsStats['Trox']?.totalFiles || 0}</span>
            </div>
            <div className="brand-stat-item">
              <span className="brand-stat-label">Páginas</span>
              <span className="brand-stat-value">{brandsStats['Trox']?.indexedPages || 0} / {brandsStats['Trox']?.totalPages || 0}</span>
            </div>
          </div>
          <div className="progress-bar-container">
            <div className="progress-bar-fill" style={{ width: `${brandsStats['Trox']?.progress || 0}%` }}></div>
          </div>
          <div className="metric-subtext" style={{ textAlign: 'right', fontWeight: '600' }}>
            {(brandsStats['Trox']?.progress || 0).toFixed(1)}%
          </div>
        </div>
      </div>

      {/* EXPLORER CARD */}
      <div className="glass-card explorer-card">
        <div className="explorer-title-row">
          <div className="explorer-title">
            <Filter size={20} className="text-secondary" />
            <h2>Explorador de Arquivos</h2>
          </div>
          <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
            Exibindo {filteredFiles.length} de {totalLocalFiles} arquivos
          </div>
        </div>

        {/* FILTERS */}
        <div className="filter-bar">
          <div className="search-input-wrapper">
            <Search className="search-icon" size={16} />
            <input 
              type="text" 
              placeholder="Buscar pelo nome do arquivo ou caminho..." 
              className="search-input"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
          </div>

          <select 
            className="select-filter" 
            value={brandFilter}
            onChange={(e) => setBrandFilter(e.target.value)}
          >
            <option value="All">Todas as Marcas</option>
            <option value="Armacell">Armacell</option>
            <option value="Daikin">Daikin</option>
            <option value="Trox">Trox</option>
          </select>

          <select 
            className="select-filter" 
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
          >
            <option value="All">Todos os Status</option>
            <option value="completed">Concluídos</option>
            <option value="partial">Parciais</option>
            <option value="pending">Pendentes</option>
          </select>
        </div>

        {/* FILE TABLE */}
        <div className="table-wrapper">
          {filteredFiles.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '3rem', color: 'var(--text-muted)' }}>
              Nenhum arquivo corresponde aos filtros selecionados.
            </div>
          ) : (
            <table>
              <thead>
                <tr>
                  <th>Arquivo</th>
                  <th>Marca</th>
                  <th>Progresso</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {filteredFiles.map((file, idx) => {
                  const pct = file.total_paginas > 0 ? (file.paginas_indexadas / file.total_paginas) * 100 : 0;
                  
                  return (
                    <tr key={idx}>
                      <td>
                        <div className="file-name-cell">
                          <span className="file-name" title={file.nome_arquivo}>{file.nome_arquivo}</span>
                          <span className="file-path" title={file.caminho_arquivo}>{file.caminho_arquivo}</span>
                        </div>
                      </td>
                      <td>
                        <span style={{ 
                          color: file.marca === 'Armacell' ? 'var(--color-armacell)' : 
                                 file.marca === 'Daikin' ? 'var(--color-daikin)' : 'var(--color-trox)',
                          fontWeight: '600',
                          fontSize: '0.85rem'
                        }}>
                          {file.marca}
                        </span>
                      </td>
                      <td style={{ width: '25%' }}>
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
                          <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                            {file.paginas_indexadas} / {file.total_paginas} págs. ({pct.toFixed(0)}%)
                          </span>
                          <div className="progress-bar-container" style={{ height: '6px' }}>
                            <div 
                              className="progress-bar-fill" 
                              style={{ 
                                width: `${pct}%`,
                                backgroundColor: file.marca === 'Armacell' ? 'var(--color-armacell)' : 
                                                 file.marca === 'Daikin' ? 'var(--color-daikin)' : 'var(--color-trox)'
                              }}
                            ></div>
                          </div>
                        </div>
                      </td>
                      <td>
                        <span className={`badge ${file.status}`}>
                          {file.status === 'completed' ? 'Concluído' :
                           file.status === 'partial' ? 'Parcial' : 'Pendente'}
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>
      </div>

      {/* FOOTER */}
      <footer>
        <p>RETEC Engenharia &copy; {new Date().getFullYear()} — Painel de Integração de Catálogos Técnicos (Setor Orçamentos)</p>
      </footer>
    </div>
  );
}

export default App;
