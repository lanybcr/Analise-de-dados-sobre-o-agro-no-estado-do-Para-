"""Análise da base tratada + geração do dashboard.

Uso:
    python src/analise.py [--base data/tratado/Culturas_Para_2016-2025_limpo.xlsx]
                          [--template src/dashboard_template.html] [--saida index.html]

O que faz:
  1. lê a base tratada (saída de src/tratamento_pam.py);
  2. deflaciona o valor da produção pelo IPCA (a preços médios de 2025);
  3. calcula os números das descobertas e imprime no terminal;
  4. grava data/apoio/estado_produto_ano_real.csv e data/dashboard_data.json;
  5. gera o index.html injetando os dados no template.

O deflator fica em data/apoio/ipca_deflator.csv. Se o arquivo não existir, o script
baixa a série do IPCA (SIDRA, tabela 1737, variável 2266 - número-índice) e o cria.
"""
import argparse, json, os, sys
import numpy as np
import pandas as pd

AQUI = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFLATOR = os.path.join(AQUI, 'data', 'apoio', 'ipca_deflator.csv')
ANO_BASE = 2025  # preços de referência
URL_IPCA = 'https://apisidra.ibge.gov.br/values/t/1737/n1/1/v/2266/p/{}01-{}12'

# culturas com série própria no dashboard; as demais entram em "outras"
CHAVES = {'Soja (em grão)': 'soja', 'Milho (em grão)': 'milho', 'Açaí': 'acai',
          'Cacau (em amêndoa)': 'cacau', 'Dendê (cacho de coco)': 'dende', 'Mandioca': 'mandioca'}
ORDEM = ['soja', 'milho', 'acai', 'cacau', 'dende', 'mandioca', 'outras']


def curto(p):
    for s in [' (em grão)', ' (em amêndoa)', ' (cacho de coco)', ' (cacho)', ' (em casca)', ' (fibra)', ' (semente)']:
        p = p.replace(s, '')
    return p


def deflator(anos):
    """Fator que leva o valor de cada ano a preços médios de ANO_BASE."""
    if os.path.exists(DEFLATOR):
        d = pd.read_csv(DEFLATOR, sep=';', decimal=',', encoding='utf-8-sig').set_index('ano')
        if set(anos) <= set(d.index):
            return d.fator_2025
    print('Baixando o IPCA do SIDRA...')
    import urllib.request
    url = URL_IPCA.format(min(anos), max(anos))
    with urllib.request.urlopen(url, timeout=60) as r:
        bruto = json.load(r)
    s = pd.DataFrame([(x['D3C'][:4], float(x['V'])) for x in bruto[1:]], columns=['ano', 'idx'])
    m = s.astype({'ano': int}).groupby('ano').idx.mean()
    if len(m) < len(anos):
        raise SystemExit('IPCA incompleto para o período; confira a conexão ou a tabela 1737.')
    d = pd.DataFrame({'ipca_indice_medio_ano': m, f'fator_{ANO_BASE}': (m[ANO_BASE] / m).round(6)})
    os.makedirs(os.path.dirname(DEFLATOR), exist_ok=True)
    d.to_csv(DEFLATOR, sep=';', decimal=',', encoding='utf-8-sig')
    return d[f'fator_{ANO_BASE}']


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--base', default=os.path.join(AQUI, 'data/tratado/Culturas_Para_2016-2025_limpo.xlsx'))
    ap.add_argument('--template', default=os.path.join(AQUI, 'src/dashboard_template.html'))
    ap.add_argument('--saida', default=os.path.join(AQUI, 'index.html'))
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding='utf-8')

    xl = pd.ExcelFile(a.base)
    F = xl.parse('producao')
    T = xl.parse('totais_municipio')
    F = F[~F.flag_subcomponente]  # café Arábica/Canephora já estão no Café Total
    anos = [int(x) for x in sorted(F.ano.unique())]
    fator = deflator(anos)
    print(f'Deflator IPCA (preços de {ANO_BASE}): ' + ', '.join(f'{y}={fator[y]:.3f}' for y in anos))

    # ---- valor real ----
    F['valor_real'] = F.valor_mil_reais * F.ano.map(fator)
    T['valor_total_real'] = T.valor_total_mil_reais * T.ano.map(fator)
    F['k'] = F.produto.map(CHAVES).fillna('outras')

    E = F.groupby(['produto', 'grupo', 'ano']).agg(
        area_ha=('area_ha', 'sum'), valor_nominal=('valor_mil_reais', 'sum'),
        valor_real=('valor_real', 'sum'), n_municipios=('area_ha', lambda s: (s > 0).sum())).reset_index()
    E = E[E.n_municipios > 0]
    E['valor_por_ha_reais'] = np.where(E.area_ha > 0, E.valor_real / E.area_ha * 1000, np.nan).round(0)
    os.makedirs(os.path.join(AQUI, 'data/apoio'), exist_ok=True)
    E.to_csv(os.path.join(AQUI, 'data/apoio/estado_produto_ano_real.csv'), index=False, sep=';', decimal=',', encoding='utf-8-sig')

    a_ = E.pivot_table(index='produto', columns='ano', values='area_ha')
    vr = E.pivot_table(index='produto', columns='ano', values='valor_real')
    vn = E.pivot_table(index='produto', columns='ano', values='valor_nominal')
    tt = T.groupby('ano')[['area_total_ha', 'valor_total_mil_reais', 'valor_total_real']].sum()
    y0, y1 = anos[0], anos[-1]

    # ---- achados ----
    print(f'\nValor {y0}->{y1}: nominal R$ {tt.valor_total_mil_reais[y0]/1e6:.1f} bi -> {tt.valor_total_mil_reais[y1]/1e6:.1f} bi '
          f'({tt.valor_total_mil_reais[y1]/tt.valor_total_mil_reais[y0]:.2f}x) | '
          f'real R$ {tt.valor_total_real[y0]/1e6:.1f} bi -> {tt.valor_total_real[y1]/1e6:.1f} bi '
          f'({tt.valor_total_real[y1]/tt.valor_total_real[y0]:.2f}x, preços de {ANO_BASE})')
    print(f'Área {y0}->{y1}: {tt.area_total_ha[y0]/1e6:.2f} -> {tt.area_total_ha[y1]/1e6:.2f} mi ha '
          f'({tt.area_total_ha[y1]/tt.area_total_ha[y0]:.2f}x). Atenção: área plantada conta cultivos sucessivos no mesmo terreno.')
    dv = (vr[y1].fillna(0) - vr[y0].fillna(0)).sort_values(ascending=False)
    da = (a_[y1].fillna(0) - a_[y0].fillna(0)).sort_values(ascending=False)
    tot_dv, tot_da = tt.valor_total_real[y1] - tt.valor_total_real[y0], tt.area_total_ha[y1] - tt.area_total_ha[y0]
    print(f'\nValor real a mais: R$ {tot_dv/1e6:.1f} bi. Top 3 = {dv.head(3).sum()/tot_dv:.0%}')
    for p, v in dv.head(6).items():
        print(f'  {curto(p):<12} +R$ {v/1e6:5.2f} bi ({v/tot_dv:5.1%})')
    print(f'\nÁrea plantada a mais: {tot_da/1e3:.0f} mil ha. Soja+milho = {(da.get("Soja (em grão)",0)+da.get("Milho (em grão)",0))/tot_da:.0%}')
    for p, v in list(da.head(5).items()) + list(da.tail(3).items()):
        print(f'  {curto(p):<12} {v/1e3:+7.0f} mil ha')
    sh = []
    for p in list(CHAVES) + ['Pimenta-do-reino', 'Abacaxi']:
        sh.append([curto(p), round(a_.loc[p, y1] / a_[y1].sum() * 100, 1), round(vr.loc[p, y1] / vr[y1].sum() * 100, 1),
                   round(vr.loc[p, y1] / a_.loc[p, y1] * 1000), CHAVES.get(p, 'outras')])
    print('\nParticipação em ' + str(y1) + ' (cultura, % área, % valor, R$/ha):')
    for s in sh:
        print(f'  {s[0]:<17} {s[1]:5.1f}% {s[2]:5.1f}%  R$ {s[3]:,}'.replace(',', '.'))
    if 2024 in anos and 2023 in anos:
        c = 'Cacau (em amêndoa)'
        print(f'\nCacau 2023->2024: nominal {vn.loc[c,2024]/vn.loc[c,2023]:.2f}x, real {vr.loc[c,2024]/vr.loc[c,2023]:.2f}x, '
              f'área {a_.loc[c,2024]/a_.loc[c,2023]-1:+.1%}')
    soja_mun = E[E.produto == 'Soja (em grão)'].set_index('ano').n_municipios
    print(f'Municípios com soja: {soja_mun[y0]} -> {soja_mun[y1]}')
    lid = lambda y: T[T.ano == y].produto_lider_valor.value_counts()
    l0, l1 = lid(y0), lid(y1)
    print('Cultura líder em valor, nº de municípios ' + f'({y0} -> {y1}): ' +
          ', '.join(f'{curto(p)} {int(l0.get(p,0))}->{int(l1.get(p,0))}' for p in ['Mandioca', 'Açaí', 'Soja (em grão)', 'Cacau (em amêndoa)', 'Pimenta-do-reino', 'Banana (cacho)']))

    # ---- dados do dashboard ----
    r = lambda s, d=0: [None if pd.isna(v) else round(float(v), d) for v in s.reindex(anos)]
    st = {'v': {}, 'vn': {}, 'a': {}}
    for k in ORDEM:
        g = F[F.k == k].groupby('ano')[['area_ha', 'valor_mil_reais', 'valor_real']].sum()
        st['v'][k], st['vn'][k], st['a'][k] = r(g.valor_real), r(g.valor_mil_reais), r(g.area_ha)
    D = {'years': anos, 'state': st, 'tv': r(tt.valor_total_real), 'tvn': r(tt.valor_total_mil_reais),
         'ta': r(tt.area_total_ha), 'ntot': r(T[T.total_status != 'indisponivel'].groupby('ano').size()),
         'deflator': {str(y): round(float(fator[y]), 4) for y in anos}, 'ano_base': ANO_BASE,
         'dv': [[curto(p), round(v / 1e6, 2), CHAVES.get(p, 'outras')] for p, v in dv.head(8).items()] +
               [['Demais culturas', round(dv.iloc[8:].sum() / 1e6, 2), 'outras']],
         'da': [[curto(p), round(v / 1e3, 1), CHAVES.get(p, 'outras')] for p, v in da.head(6).items()] +
               [[curto(p), round(v / 1e3, 1), CHAVES.get(p, 'outras')] for p, v in da.tail(3).items()],
         'dv_tot': round(tot_dv / 1e6, 2), 'da_tot': round(tot_da / 1e3, 0), 'share': sh,
         'sojamilho': [round(x, 1) for x in ((a_.loc['Soja (em grão)'] + a_.loc['Milho (em grão)']) / a_.sum() * 100).reindex(anos)],
         'sojamun': r(soja_mun),
         'lead': [[curto(p), int(l0.get(p, 0)), int(l1.get(p, 0)), CHAVES.get(p, 'outras')] for p in
                  ['Mandioca', 'Açaí', 'Soja (em grão)', 'Cacau (em amêndoa)', 'Pimenta-do-reino', 'Banana (cacho)', 'Dendê (cacho de coco)', 'Milho (em grão)']]}
    rk = {}
    for y in anos:
        t = T[(T.ano == y) & T.valor_total_real.notna()].sort_values('valor_total_real', ascending=False)
        soma = t.valor_total_real.sum()
        rk[y] = [[m, round(v / 1e6, 3), int(ar), curto(str(l)), round(v / soma * 100, 1)]
                 for m, v, ar, l in t.head(10)[['municipio', 'valor_total_real', 'area_total_ha', 'produto_lider_valor']].values]
    D['rank'] = rk
    mv = F.pivot_table(index=['municipio', 'k'], columns='ano', values='valor_real', aggfunc=lambda s: s.sum(min_count=1))
    Tm = T.set_index(['municipio', 'ano'])
    D['mun'] = {m: {'v': {k: (r(mv.loc[(m, k)]) if (m, k) in mv.index else [None] * len(anos)) for k in ORDEM},
                    't': r(Tm.loc[m].valor_total_real), 'a': r(Tm.loc[m].area_total_ha)}
                for m in sorted(T.municipio.unique())}
    os.makedirs(os.path.join(AQUI, 'data'), exist_ok=True)
    json.dump(D, open(os.path.join(AQUI, 'data/dashboard_data.json'), 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))

    tpl = open(a.template, encoding='utf-8').read()
    if '/*DATA*/' not in tpl:
        raise SystemExit('template sem o marcador /*DATA*/')
    open(a.saida, 'w', encoding='utf-8').write(tpl.replace('/*DATA*/', json.dumps(D, ensure_ascii=False, separators=(',', ':'))))
    print(f'\nGerados: data/dashboard_data.json e {os.path.basename(a.saida)}')


if __name__ == '__main__':
    main()
