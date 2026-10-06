"""Gera o modelo estrela (fProducao, dMunicipio, dCultura, dTempo) para o Power BI.

Entrada : data/tratado/Culturas_Para_2016-2025_producao.csv e data/apoio/ipca_deflator.csv
Saída   : data/modelo/{fProducao,dMunicipio,dCultura,dTempo}.csv

Granularidade de fProducao: município x ano x cultura, só onde há cultivo ou o dado está
indisponível. Linhas "sem cultivo" (zero) são omitidas: no Power BI a ausência de linha
já significa zero, e a tabela cai de 62.921 para ~23 mil linhas.
"""
import argparse
import os
import sys

import pandas as pd

AQUI = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def principal():
    p = argparse.ArgumentParser()
    p.add_argument('--producao', default=os.path.join(AQUI, 'data/tratado/Culturas_Para_2016-2025_producao.csv'))
    p.add_argument('--deflator', default=os.path.join(AQUI, 'data/apoio/ipca_deflator.csv'))
    p.add_argument('--saida', default=os.path.join(AQUI, 'data/modelo'))
    a = p.parse_args()
    sys.stdout.reconfigure(encoding='utf-8')
    os.makedirs(a.saida, exist_ok=True)

    P = pd.read_csv(a.producao, sep=';', decimal=',', encoding='utf-8-sig')
    D = pd.read_csv(a.deflator, sep=';', decimal=',', encoding='utf-8-sig')

    # dTempo
    dT = D[['ano', 'fator_2025']].rename(columns={'fator_2025': 'fator_deflator_2025'})
    dT['ano_preliminar'] = dT.ano.isin(P.loc[P.ano_preliminar, 'ano'].unique())
    dT = dT.sort_values('ano').reset_index(drop=True)

    # dMunicipio
    dM = P[['municipio', 'uf']].drop_duplicates().sort_values('municipio').reset_index(drop=True)
    dM.insert(0, 'id_municipio', dM.index + 1)

    # dCultura (inclui flags de qualidade para filtrar no DAX)
    cols = ['produto', 'grupo', 'tipo_cultura', 'flag_subcomponente', 'flag_produto_inicio_tardio']
    dC = P[cols].drop_duplicates('produto').sort_values('produto').reset_index(drop=True)
    dC.insert(0, 'id_cultura', dC.index + 1)

    # fProducao
    F = P[P.situacao != 'sem_cultivo'].merge(dM[['id_municipio', 'municipio']], on='municipio') \
                                      .merge(dC[['id_cultura', 'produto']], on='produto') \
                                      .merge(dT[['ano', 'fator_deflator_2025']], on='ano')
    F['valor_real_mil_reais'] = (F.valor_mil_reais * F.fator_deflator_2025).round(1)
    F = F[['id_municipio', 'id_cultura', 'ano', 'situacao', 'area_ha', 'valor_mil_reais', 'valor_real_mil_reais',
           'flag_area_sem_valor', 'flag_salto_area', 'flag_outlier_valor_ha']] \
        .sort_values(['ano', 'id_municipio', 'id_cultura']).reset_index(drop=True)

    # checagens de integridade
    assert not F.duplicated(['id_municipio', 'id_cultura', 'ano']).any(), 'chave duplicada em fProducao'
    assert F[['id_municipio', 'id_cultura', 'ano']].notna().all().all(), 'chave nula'
    assert set(F.ano) <= set(dT.ano), 'ano fora de dTempo'

    for nome, df in [('fProducao', F), ('dMunicipio', dM), ('dCultura', dC), ('dTempo', dT)]:
        df.to_csv(os.path.join(a.saida, nome + '.csv'), index=False, sep=';', decimal=',', encoding='utf-8-sig')
        print(f'{nome}: {len(df):,} linhas, {len(df.columns)} colunas')

    # reconciliação com a base tratada: valor nominal e área batem
    ref = P[P.situacao == 'cultivado']
    print('Área (ha) fProducao vs base:', round(F.area_ha.sum()), round(ref.area_ha.sum()))
    print('Valor (mil R$) fProducao vs base:', round(F.valor_mil_reais.sum()), round(P.valor_mil_reais.sum()))


if __name__ == '__main__':
    principal()
