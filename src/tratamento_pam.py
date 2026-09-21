"""Tratamento de exportações do SIDRA (Produção Agrícola Municipal, tabela 5457).

Uso:
    python tratamento_pam.py ARQ1.xlsx ARQ2.xlsx ... [--saida PASTA] [--prefixo NOME]

Cada arquivo tem 3 abas (área, % da área, valor) com município nas linhas e ano x produto
nas colunas. O script junta todos os arquivos (períodos diferentes), trata, valida e gera:
  <prefixo>_limpo.xlsx (7 abas) e 3 CSVs (produção, totais por município, estado por produto).
"""
import argparse, os, sys
import numpy as np
import pandas as pd

GRUPOS = {
 'Grãos e oleaginosas': ['Arroz (em casca)','Aveia (em grão)','Centeio (em grão)','Cevada (em grão)','Milho (em grão)','Sorgo (em grão)','Trigo (em grão)','Triticale (em grão)','Soja (em grão)','Girassol (em grão)','Canola','Amendoim (em casca)','Gergelim','Mamona (baga)','Feijão (em grão)','Ervilha (em grão)','Fava (em grão)','Linho (semente)'],
 'Raízes e tubérculos': ['Mandioca','Batata-doce','Batata-inglesa','Inhame'],
 'Hortaliças': ['Abóbora','Alface','Alho','Cebola','Cenoura','Chuchu','Milho verde','Pimentão','Repolho','Tomate'],
 'Frutas': ['Abacate','Abacaxi','Acerola','Açaí','Banana (cacho)','Caju','Caqui','Coco-da-baía','Cupuaçu','Figo','Goiaba','Graviola','Laranja','Limão','Maçã','Mamão','Manga','Maracujá','Marmelo','Melancia','Melão','Morango','Pera','Pêssego','Tangerina','Uva','Azeitona'],
 'Cana e forragens': ['Cana-de-açúcar','Cana para forragem','Alfafa fenada'],
 'Perenes comerciais': ['Cacau (em amêndoa)','Café (em grão) Total','Café (em grão) Arábica','Café (em grão) Canephora','Dendê (cacho de coco)','Borracha (látex coagulado)','Borracha (látex líquido)','Guaraná (semente)','Pimenta-do-reino','Erva-mate (folha verde)','Chá-da-índia (folha verde)','Urucum (semente)','Castanha de caju','Noz (fruto seco)','Tungue (fruto seco)','Palmito'],
 'Fibras e fumo': ['Algodão arbóreo (em caroço)','Algodão herbáceo (em caroço)','Juta (fibra)','Malva (fibra)','Rami (fibra)','Sisal ou agave (fibra)','Fumo (em folha)'],
}
GRUPO = {p: g for g, l in GRUPOS.items() for p in l}
PERMANENTES = set(['Abacate','Açaí','Acerola','Algodão arbóreo (em caroço)','Azeitona','Banana (cacho)','Borracha (látex coagulado)','Borracha (látex líquido)','Cacau (em amêndoa)','Café (em grão) Total','Café (em grão) Arábica','Café (em grão) Canephora','Caju','Caqui','Castanha de caju','Chá-da-índia (folha verde)','Coco-da-baía','Cupuaçu','Dendê (cacho de coco)','Erva-mate (folha verde)','Figo','Goiaba','Graviola','Guaraná (semente)','Laranja','Limão','Maçã','Mamão','Manga','Maracujá','Marmelo','Noz (fruto seco)','Palmito','Pera','Pêssego','Pimenta-do-reino','Tangerina','Tungue (fruto seco)','Urucum (semente)','Uva'])
SUBCOMPONENTES = {'Café (em grão) Arábica', 'Café (em grão) Canephora'}


def ler_arquivo(caminho):
    """Lê as 3 abas de uma exportação e devolve formato longo (município x ano x produto)."""
    xl = pd.ExcelFile(caminho)
    partes = {}
    for aba in xl.sheet_names:
        d = pd.read_excel(xl, aba, header=None, dtype=object)
        titulo = str(d.iloc[1, 0])
        if 'percentual' in titulo:
            nome = 'pct_raw'
        elif 'Valor da produ' in titulo:
            nome = 'valor_raw'
        elif 'rea plantada' in titulo:
            nome = 'area_raw'
        else:
            continue
        anos = d.iloc[3].ffill()
        prods = d.iloc[4]
        corpo = d.iloc[5:]
        corpo = corpo[corpo[0].astype(str).str.contains(r'\(PA\)', na=False)]
        blocos = [pd.DataFrame({'municipio_raw': corpo[0].values, 'ano': int(anos[c]), 'produto_raw': prods[c],
                                nome: corpo[c].astype(str).str.strip().values}) for c in range(1, d.shape[1])]
        partes[nome] = pd.concat(blocos)
    faltam = {'area_raw', 'pct_raw', 'valor_raw'} - set(partes)
    if faltam:
        raise SystemExit(f'{caminho}: abas não reconhecidas: {faltam}')
    k = ['municipio_raw', 'ano', 'produto_raw']
    return partes['area_raw'].merge(partes['pct_raw'], on=k, validate='1:1').merge(partes['valor_raw'], on=k, validate='1:1')


def tratar(arquivos):
    st = {}
    L = []
    for a in arquivos:
        d = ler_arquivo(a)
        d['arquivo'] = os.path.basename(a)
        st['arq_' + os.path.basename(a)] = (int(d.ano.min()), int(d.ano.max()), d.shape[0])
        L.append(d)
    D = pd.concat(L, ignore_index=True)
    dup = D.duplicated(['municipio_raw', 'ano', 'produto_raw']).sum()
    if dup:
        raise SystemExit(f'{dup} linhas repetidas entre arquivos: os períodos se sobrepõem')
    st['celulas'] = len(D)

    def situ(s):
        return np.where(s == '-', 'zero', np.where(s == '...', 'indisponivel', 'informado'))
    for n in ['area', 'pct', 'valor']:
        D[n + '_st'] = situ(D[n + '_raw'])
        D[n] = pd.to_numeric(D[n + '_raw'], errors='coerce')
        D.loc[D[n + '_st'] == 'zero', n] = 0.0
        assert D.loc[D[n + '_st'] == 'informado', n].notna().all(), f'texto inesperado em {n}'
    st['informado'] = int((D.area_st == 'informado').sum())
    st['zero'] = int((D.area_st == 'zero').sum())
    st['indisp'] = int((D.area_st == 'indisponivel').sum())
    D['produto'] = D.produto_raw.str.replace('*', '', regex=False).str.strip()
    D['municipio'] = D.municipio_raw.str.replace(r'\s*\(PA\)$', '', regex=True).str.strip()
    anos = sorted(D.ano.unique())
    st['anos'] = anos

    # painel completo? (todo município em todo ano x produto)
    muns_por_ano = D.groupby('ano').municipio.nunique()
    st['municipios'] = int(D.municipio.nunique())
    st['mun_por_ano_ok'] = bool((muns_por_ano == st['municipios']).all())
    desconhecidos = sorted(set(D.produto) - {'Total'} - set(GRUPO))
    st['produtos_sem_grupo'] = desconhecidos

    P = D[D.produto != 'Total'].copy()
    T = D[D.produto == 'Total'][['municipio', 'ano', 'area', 'valor', 'area_st']].rename(
        columns={'area': 'area_total_ha', 'valor': 'valor_total_mil_reais'})
    # 1) produtos nunca cultivados em nenhum município/ano do período todo
    cult = P.groupby('produto').area.apply(lambda s: (s.fillna(0) > 0).sum())
    nunca = sorted(cult[cult == 0].index)
    st['n_produtos'] = int(cult.shape[0]); st['nunca'] = nunca
    # 2) total x soma dos produtos
    comp = P[~P.produto.isin(SUBCOMPONENTES)]
    sm = comp.groupby(['municipio', 'ano']).agg(soma_area=('area', 'sum'), soma_valor=('valor', 'sum'),
                                                 n_inf=('area_st', lambda s: (s != 'indisponivel').sum())).reset_index()
    T = T.merge(sm, on=['municipio', 'ano'])
    ok = T.area_st == 'informado'
    st['total_confere'] = int(((T.area_total_ha - T.soma_area).abs() <= 1)[ok].sum()); st['total_n'] = int(ok.sum())
    st['total_ausente'] = T[~ok][['municipio', 'ano']].values.tolist()
    T['total_status'] = np.where(ok, 'informado', 'indisponivel')
    rec = (~ok) & (T.n_inf > 0)
    T.loc[rec, 'area_total_ha'] = T.loc[rec, 'soma_area']; T.loc[rec, 'valor_total_mil_reais'] = T.loc[rec, 'soma_valor']
    T.loc[rec, 'total_status'] = 'reconstruido_soma_produtos'
    st['total_reconstruido'] = int(rec.sum())
    # café
    c = P[P.produto.str.startswith('Café')].pivot_table(index=['municipio', 'ano'], columns='produto', values='area')
    if 'Café (em grão) Total' in c:
        sub = c.reindex(columns=list(SUBCOMPONENTES)).fillna(0).sum(axis=1)
        st['cafe_div'] = int(((c['Café (em grão) Total'].fillna(0) - sub).abs() > 1).sum())
    # 3) só produtos cultivados
    P = P[~P.produto.isin(nunca)].copy()
    P = P.merge(T[['municipio', 'ano', 'area_total_ha', 'valor_total_mil_reais']], on=['municipio', 'ano'])
    P['pct_recalc'] = P.area / P.area_total_ha * 100
    st['pct_n'] = int(P.pct.notna().sum())
    st['pct_diverge'] = int(((P.pct - P.pct_recalc).abs() > 0.1).sum())
    P['pct_area_total_municipio'] = P.pct.where(P.pct.notna(), P.pct_recalc)
    sv = (P.area > 0) & (P.valor_st == 'zero')
    st['area_sem_valor'] = int(sv.sum())
    P['flag_area_sem_valor'] = sv
    P.loc[sv, 'valor'] = np.nan; P.loc[sv, 'valor_st'] = 'inconsistente'
    P['valor_por_ha_reais'] = np.where((P.area > 0) & (P.valor > 0), P.valor / P.area * 1000, np.nan)
    P = P.sort_values(['municipio', 'produto', 'ano']).reset_index(drop=True)
    prev = P.groupby(['municipio', 'produto']).area.shift()
    r = P.area / prev
    P['var_area_ano_anterior_pct'] = np.where(prev > 0, (r - 1) * 100, np.nan)
    P['flag_salto_area'] = (prev > 0) & (P.area > 0) & ((r > 5) | (r < 0.2)) & ((P.area - prev).abs() >= 100)
    P['flag_outlier_valor_ha'] = False
    for pr, g in P[P.valor_por_ha_reais.notna()].groupby('produto'):
        if len(g) < 20:
            continue
        l = np.log(g.valor_por_ha_reais); q1, q3 = l.quantile([.25, .75]); i = q3 - q1
        P.loc[g.index[(l < q1 - 3 * i) | (l > q3 + 3 * i)], 'flag_outlier_valor_ha'] = True
    # 4) quebra de série: produto que só aparece depois do primeiro ano / some antes do último
    dados = P[P.area_st != 'indisponivel'].groupby('produto').ano.agg(['min', 'max'])
    com_area = P[P.area > 0].groupby('produto').ano.max()
    novos = sorted(dados[dados['min'] > anos[0]].index)
    sumiu = sorted(com_area[com_area < anos[-1]].index)
    st['novos'] = {p: int(dados.loc[p, 'min']) for p in novos}; st['sumiram'] = {p: int(com_area[p]) for p in sumiu}
    # continuidade do total estadual entre anos
    tt = T.groupby('ano')[['area_total_ha', 'valor_total_mil_reais']].sum()
    va, vv = tt.area_total_ha.pct_change() * 100, tt.valor_total_mil_reais.pct_change() * 100
    st['anos_atipicos'] = [(int(y), round(float(va[y]), 1), round(float(vv[y]), 1)) for y in tt.index[1:] if abs(vv[y]) > 30 or abs(va[y]) > 15]
    P['flag_produto_inicio_tardio'] = P.produto.isin(novos)
    P['flag_produto_encerrado'] = P.produto.isin(sumiu)
    P['flag_subcomponente'] = P.produto.isin(SUBCOMPONENTES)
    P['situacao'] = np.select([P.area_st == 'informado', P.area_st == 'zero', P.area_st == 'indisponivel'],
                              ['cultivado', 'sem_cultivo', 'indisponivel'], default='')
    P['grupo'] = P.produto.map(GRUPO).fillna('Outros')
    P['tipo_cultura'] = np.where(P.produto.isin(PERMANENTES), 'permanente', 'temporária')
    P['uf'] = 'PA'; P['ano_preliminar'] = P.ano == anos[-1]
    cols = ['municipio', 'uf', 'ano', 'ano_preliminar', 'produto', 'grupo', 'tipo_cultura', 'situacao', 'area', 'pct_area_total_municipio',
            'valor', 'valor_por_ha_reais', 'var_area_ano_anterior_pct', 'area_total_ha', 'valor_total_mil_reais',
            'flag_area_sem_valor', 'flag_salto_area', 'flag_outlier_valor_ha', 'flag_produto_inicio_tardio', 'flag_produto_encerrado', 'flag_subcomponente']
    F = P[cols].rename(columns={'area': 'area_ha', 'valor': 'valor_mil_reais'})
    F['pct_area_total_municipio'] = F.pct_area_total_municipio.round(2)
    F['valor_por_ha_reais'] = F.valor_por_ha_reais.round(0)
    F['var_area_ano_anterior_pct'] = F.var_area_ano_anterior_pct.round(1)
    assert not F.duplicated(['municipio', 'ano', 'produto']).any()
    st['flags'] = {c: int(F[c].sum()) for c in F if c.startswith('flag')}
    st['linhas'] = len(F); st['n_prod_final'] = int(F.produto.nunique())
    return D, F, T, st, nunca


def tabelas_apoio(F, T):
    base = F[~F.flag_subcomponente]
    g = base[base.area_ha > 0].groupby(['municipio', 'ano'])
    TM = g.agg(n_produtos_cultivados=('produto', 'nunique')).reset_index()
    TM['hhi_area'] = g.apply(lambda x: ((x.area_ha / x.area_ha.sum()) ** 2).sum(), include_groups=False).values.round(3)
    lead = (base[base.valor_mil_reais.notna()].sort_values('valor_mil_reais', ascending=False)
            .drop_duplicates(['municipio', 'ano'])[['municipio', 'ano', 'produto', 'valor_mil_reais']]
            .rename(columns={'produto': 'produto_lider_valor', 'valor_mil_reais': 'valor_produto_lider'}))
    gr = base.groupby(['municipio', 'ano', 'grupo']).area_ha.sum().unstack().add_prefix('area_ha_').reset_index()
    T2 = (T[['municipio', 'ano', 'area_total_ha', 'valor_total_mil_reais', 'total_status']]
          .merge(TM, on=['municipio', 'ano'], how='left').merge(lead, on=['municipio', 'ano'], how='left')
          .merge(gr, on=['municipio', 'ano'], how='left'))
    T2['uf'] = 'PA'; T2['ano_preliminar'] = T2.ano == T2.ano.max()
    sm = base[base.produto.isin(['Soja (em grão)', 'Milho (em grão)'])].groupby(['municipio', 'ano']).area_ha.sum()
    T2['pct_soja_milho_area'] = (sm.reindex(pd.MultiIndex.from_frame(T2[['municipio', 'ano']])).values / T2.area_total_ha * 100).round(1)
    T2['valor_por_ha_reais'] = (T2.valor_total_mil_reais / T2.area_total_ha * 1000).round(0)
    E = base.groupby(['produto', 'grupo', 'tipo_cultura', 'ano']).agg(
        area_ha=('area_ha', 'sum'), valor_mil_reais=('valor_mil_reais', 'sum'),
        n_municipios=('area_ha', lambda s: (s > 0).sum())).reset_index()
    tot = E.groupby('ano')[['area_ha', 'valor_mil_reais']].transform('sum')
    E['pct_area_estado'] = (E.area_ha / tot.area_ha * 100).round(2)
    E['pct_valor_estado'] = (E.valor_mil_reais / tot.valor_mil_reais * 100).round(2)
    E['valor_por_ha_reais'] = np.where(E.area_ha > 0, E.valor_mil_reais / E.area_ha * 1000, np.nan).round(0)
    E = E[E.n_municipios > 0]
    return T2, E


def produtos(D, F, nunca, anos):
    linhas = []
    todos = sorted(set(D.produto) - {'Total'})
    for p in todos:
        x = F[F.produto == p]
        g = GRUPO.get(p, 'Outros'); t = 'permanente' if p in PERMANENTES else 'temporária'
        if x.empty:
            linhas.append([p, g, t, f'excluído: nunca cultivado em {anos[0]}–{anos[-1]}', None, None, None]); continue
        inf = x[x.situacao != 'indisponivel']; cult = x[x.area_ha > 0]
        obs = []
        if x.flag_produto_inicio_tardio.any(): obs.append(f'sem dado antes de {int(inf.ano.min())} (quebra de série)')
        if x.flag_produto_encerrado.any(): obs.append(f'sem área depois de {int(cult.ano.max())}')
        if p in SUBCOMPONENTES: obs.append('subcomponente do Café Total (não somar)')
        linhas.append([p, g, t, '; '.join(obs) or 'ok', int(inf.ano.min()) if len(inf) else None,
                       int(cult.ano.max()) if len(cult) else None, int((x[x.ano == anos[-1]].area_ha > 0).sum())])
    return pd.DataFrame(linhas, columns=['produto', 'grupo', 'tipo_cultura', 'observacao', 'primeiro_ano_com_dado', 'ultimo_ano_com_area', f'municipios_cultivando_{anos[-1]}'])


DICIONARIO = [
 ('municipio', 'texto', 'Município, sem o sufixo "(PA)"'), ('uf', 'texto', 'UF (PA)'), ('ano', 'inteiro', 'Ano de referência'),
 ('ano_preliminar', 'booleano', 'VERDADEIRO no último ano da base (resultado preliminar, nota 13 do IBGE)'),
 ('produto', 'texto', 'Cultura com alguma área no período. Nomes sem asterisco'),
 ('grupo', 'texto', 'Agrupamento analítico criado pelo tratamento (não vem do IBGE)'),
 ('tipo_cultura', 'texto', 'permanente ou temporária, conforme a classificação usual do IBGE'),
 ('situacao', 'texto', 'cultivado = área > 0; sem_cultivo = "-" no original (zero); indisponivel = "..." no original (nulo)'),
 ('area_ha', 'número', 'Área plantada ou destinada à colheita (ha). 0 = sem cultivo; vazio = indisponível'),
 ('pct_area_total_municipio', 'número', 'Área do produto ÷ área total do município × 100 (valor do IBGE, conferido por recálculo)'),
 ('valor_mil_reais', 'número', 'Valor da produção, mil reais correntes (nominais). Vazio se indisponível ou inconsistente'),
 ('valor_por_ha_reais', 'número', 'Valor ÷ área, R$/ha (só onde área > 0 e valor > 0)'),
 ('var_area_ano_anterior_pct', 'número', 'Variação % da área sobre o ano anterior (só onde o ano anterior > 0)'),
 ('area_total_ha', 'número', 'Área total de lavouras do município no ano (todos os produtos)'),
 ('valor_total_mil_reais', 'número', 'Valor total da produção do município no ano (mil R$)'),
 ('flag_area_sem_valor', 'booleano', 'Área > 0 mas valor "-" no original; valor anulado'),
 ('flag_salto_area', 'booleano', 'Área multiplicou por mais de 5 ou caiu abaixo de 1/5 do ano anterior. A revisar, não corrigido'),
 ('flag_outlier_valor_ha', 'booleano', 'R$/ha fora de 3×IQR (escala log) dentro do produto. A revisar, não corrigido'),
 ('flag_produto_inicio_tardio', 'booleano', 'Produto sem dado nos primeiros anos da base: quebra de série, não comparar com os anos sem dado'),
 ('flag_produto_encerrado', 'booleano', 'Produto sem dado nos últimos anos da base'),
 ('flag_subcomponente', 'booleano', 'Café Arábica e Canephora, já incluídos no Café Total. NÃO somar: filtrar este flag = falso'),
]
DIC_TOTAIS = [('total_status', 'informado, reconstruido_soma_produtos ou indisponivel'), ('n_produtos_cultivados', 'Produtos com área > 0 (sem contar os subcomponentes do café)'),
 ('hhi_area', 'Concentração da área entre produtos (0 a 1). Perto de 1 = quase monocultura'), ('produto_lider_valor', 'Produto de maior valor no município/ano'),
 ('area_ha_<grupo>', 'Área por grupo de cultura'), ('pct_soja_milho_area', '% da área do município ocupada por soja e milho'), ('valor_por_ha_reais', 'Valor total ÷ área total')]


def montar_log(st, extra=None):
    n = st['celulas']; a0, a1 = st['anos'][0], st['anos'][-1]
    f = lambda x: f'{x:,}'.replace(',', '.')
    L = [
     ('Estrutura', 'Cada arquivo tem 3 abas (área, % da área, valor), cabeçalho de 3 níveis, células mescladas, rodapé e notas', f'{len(st) and sum(1 for k in st if k.startswith("arq_"))} arquivo(s) lidos e juntados em formato longo (1 linha = município × ano × produto). Junção das 3 abas conferida 1 para 1; sem linhas repetidas entre arquivos'),
     ('Estrutura', 'Município com "(PA)"; asteriscos em "Abacaxi*" e "Coco-da-baía*"', 'Sufixo separado em coluna uf; asteriscos removidos'),
     ('Estrutura', 'Ano em cabeçalho mesclado', 'Preenchido para cada coluna e convertido em inteiro'),
     ('Tipos', 'Números misturados com texto', f'Convertidos para número. De {f(n)} células por variável, {f(st["informado"])} ({st["informado"]/n:.0%}) tinham número; {f(st["zero"])} eram "-" e {f(st["indisp"])} eram "..."'),
     ('Faltantes', '"-"', 'Convertido em 0 e situacao = sem_cultivo'),
     ('Faltantes', '"..."', 'Convertido em nulo e situacao = indisponivel. Nunca em zero'),
     ('Cobertura', f'{st["n_produtos"]} produtos no arquivo, {len(st["nunca"])} nunca cultivados em {a0}–{a1}', f'Removidos da base analítica; {st["n_prod_final"]} produtos e {f(st["linhas"])} linhas restam. Todos listados na aba produtos'),
     ('Painel', f'{st["municipios"]} municípios', 'Todos aparecem em todos os anos' if st['mun_por_ano_ok'] else 'ATENÇÃO: nem todo município aparece em todos os anos'),
    ]
    if st['novos']:
        L.append(('Quebra de série', f'{len(st["novos"])} produtos sem dado nos primeiros anos: ' + ', '.join(f'{p} (desde {y})' for p, y in st['novos'].items()), 'Marcados com flag_produto_inicio_tardio. Não comparar com os anos sem dado'))
    if st['sumiram']:
        L.append(('Quebra de série', f'{len(st["sumiram"])} produtos sem área no último ano: ' + ', '.join(f'{p} (até {y})' for p, y in st['sumiram'].items()), 'Marcados com flag_produto_encerrado'))
    L += [
     ('Duplicidade', 'Café (em grão) Total = Arábica + Canephora' + (f' ({st.get("cafe_div",0)} divergências)'), 'Arábica e Canephora marcados com flag_subcomponente. Somar sem esse filtro contaria o café duas vezes'),
     ('Total', f'Total do município fecha com a soma dos produtos em {st["total_confere"]} de {st["total_n"]} casos', 'Confirma que a base cobre todas as lavouras do estado' if st['total_confere'] == st['total_n'] else 'ATENÇÃO: há divergências'),
     ('Total ausente', f'{len(st["total_ausente"])} município-anos sem Total: ' + ', '.join(f'{m} {a}' for m, a in st['total_ausente'][:8]), f'{st["total_reconstruido"]} reconstruídos pela soma dos produtos; os demais ficam nulos (total_status = indisponivel)'),
     ('Percentual', 'Aba de % do total é redundante com a de área', f'Recalculei {f(st["pct_n"])} registros: {st["pct_diverge"]} divergências acima de 0,1 ponto. Mantido o valor do IBGE'),
     ('Área sem valor', f'{st["area_sem_valor"]} casos com área > 0 e valor "-"', 'Valor anulado (nulo, não zero) e marcado em flag_area_sem_valor'),
     ('Outliers', f'{st["flags"]["flag_salto_area"]} saltos de área (>5× ou <1/5) e {st["flags"]["flag_outlier_valor_ha"]} valores por hectare atípicos', 'SINALIZADOS, não corrigidos. Salto de área só conta se a variação for de 100 ha ou mais (evita ruído de áreas minúsculas). Aba a_revisar lista as linhas com algum alerta'),
     ('Variáveis novas', '—', 'grupo, tipo_cultura, valor_por_ha_reais, var_area_ano_anterior_pct, ano_preliminar; nas abas de apoio: n_produtos_cultivados, hhi_area, produto_lider_valor, pct_soja_milho_area'),
     ('Não feito', 'Inflação; código IBGE; quantidade produzida e rendimento', 'Valores continuam nominais (precisa de um deflator como o IPCA); sem código IBGE por falta de tabela de apoio; quantidade e rendimento nunca estiveram no arquivo'),
    ]
    if st['anos_atipicos']:
        L.append(('Continuidade', 'Variação do total estadual: ' + '; '.join(f'{y}: área {va:+.1f}%, valor {vv:+.1f}%' for y, va, vv in st['anos_atipicos']), 'Nenhuma quebra na junção dos arquivos, mas esses anos merecem atenção (valor cresce muito mais que a área: preço ou mudança de metodologia). Não corrigido'))
    L += extra or []
    return pd.DataFrame(L, columns=['tema', 'problema', 'ação'])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('arquivos', nargs='+'); ap.add_argument('--saida', default='.'); ap.add_argument('--prefixo', default='Culturas_Para_limpo')
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding='utf-8')
    D, F, T, st, nunca = tratar(a.arquivos)
    T2, E = tabelas_apoio(F, T)
    PROD = produtos(D, F, nunca, st['anos'])
    REV = F[F.flag_area_sem_valor | F.flag_salto_area | F.flag_outlier_valor_ha]
    LOG = montar_log(st)
    os.makedirs(a.saida, exist_ok=True)
    p = os.path.join(a.saida, a.prefixo)
    for nome, df in [('producao', F), ('totais_municipio', T2), ('estado_produto_ano', E)]:
        df.to_csv(f'{p}_{nome}.csv', index=False, encoding='utf-8-sig', sep=';', decimal=',')
    dic = pd.DataFrame(DICIONARIO, columns=['coluna', 'tipo', 'descrição'])
    dicT = pd.DataFrame(DIC_TOTAIS, columns=['coluna (aba totais_municipio)', 'descrição'])
    with pd.ExcelWriter(f'{p}_limpo.xlsx', engine='openpyxl') as w:
        F.to_excel(w, sheet_name='producao', index=False); T2.to_excel(w, sheet_name='totais_municipio', index=False)
        E.to_excel(w, sheet_name='estado_produto_ano', index=False); PROD.to_excel(w, sheet_name='produtos', index=False)
        REV.to_excel(w, sheet_name='a_revisar', index=False)
        dic.to_excel(w, sheet_name='dicionario', index=False); dicT.to_excel(w, sheet_name='dicionario', index=False, startrow=len(dic) + 3)
        LOG.to_excel(w, sheet_name='log_tratamento', index=False)
        for ws in w.book.worksheets:
            ws.freeze_panes = 'A2'; ws.auto_filter.ref = ws.dimensions
            for col in ws.columns:
                ws.column_dimensions[col[0].column_letter].width = min(70, max(10, max(len(str(c.value or '')) for c in col[:300]) + 2))
    print(f'Anos {st["anos"][0]}–{st["anos"][-1]} | {st["municipios"]} municípios | {st["n_prod_final"]} produtos | {st["linhas"]} linhas')
    print('Sinalizações:', st['flags'])
    print('Novos:', st['novos'], '| Encerrados:', st['sumiram'], '| Nunca cultivados:', len(st['nunca']))
    print('Total confere:', st['total_confere'], '/', st['total_n'], '| ausentes:', st['total_ausente'])
    print(f'Arquivos gerados em {os.path.abspath(a.saida)}')


if __name__ == '__main__':
    main()
