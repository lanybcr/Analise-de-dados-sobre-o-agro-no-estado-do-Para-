# Análise de dados sobre o agro no estado do Pará

> **O agro do Pará quase quadruplicou em dez anos. A soja trouxe a terra. O açaí e o cacau trouxeram o valor.**

Análise de 44 culturas em 143 municípios paraenses entre 2016 e 2025, a partir da Produção Agrícola Municipal (PAM) do IBGE, tabela 5457 do SIDRA.

**Dashboard interativo:** abra o [`index.html`](index.html) no navegador (arquivo único, sem dependências, funciona offline). Para publicar online, ative o GitHub Pages em *Settings → Pages → Deploy from a branch → main / (root)*.

## O que a análise mostra

| Descoberta | Número |
|---|---|
| Valor da produção, 2016 → 2025 (nominal) | R$ 9,9 bi → R$ 38,4 bi (**3,9×**) |
| Área de lavouras, 2016 → 2025 | 1,57 → 3,37 milhões de ha (**2,2×**) |
| Terra nova que é soja e milho | **76%** dos 1,8 milhão de ha a mais |
| Valor novo que vem de soja, açaí e cacau | **65%** dos R$ 28,5 bi a mais |
| Açaí e cacau | 13% da área, **38%** do valor |
| Soja | 39% da área, 22% do valor |
| Cacau, 2023 → 2024 | valor **3,8×** com área +2% (preço, não terra) |
| Municípios com soja | 27 → 41 |

Explicações que dependem de informação de fora da base (por exemplo, a alta internacional do cacau) estão marcadas como **hipótese** no dashboard.

## Estrutura do repositório

```
index.html                       dashboard (HTML + SVG + JavaScript, sem bibliotecas)
data/
  raw/                           exportações originais do SIDRA (2016–2020 e 2021–2025)
  tratado/                       base limpa, pronta para análise
    Culturas_Para_2016-2025_limpo.xlsx                 7 abas: producao, totais_municipio,
                                                       estado_produto_ano, produtos, a_revisar,
                                                       dicionario, log_tratamento
    Culturas_Para_2016-2025_producao.csv               município × ano × cultura
    Culturas_Para_2016-2025_totais_municipio.csv       1 linha por município/ano
    Culturas_Para_2016-2025_estado_produto_ano.csv     agregado do estado por cultura
src/tratamento_pam.py            pipeline de tratamento (reproduz a pasta tratado/)
```

Os CSVs usam `;` como separador, vírgula decimal e UTF-8 com BOM, para abrir direto no Excel brasileiro.

## Como os dados foram tratados

Os arquivos do SIDRA são relatórios (3 abas, cabeçalho em 3 níveis, símbolos no lugar de números), não bases analíticas. O `tratamento_pam.py`:

- junta as 3 abas de cada arquivo e os dois períodos em formato longo (município × ano × cultura);
- converte `-` em **0** (sem cultivo) e `...` em **nulo** (indisponível), nunca em zero. Só 14% das células tinham número;
- remove 41 culturas nunca cultivadas no período (44 permanecem);
- marca o café Arábica e Canephora como subcomponentes do Café Total, para não contar o café duas vezes;
- sinaliza (sem corrigir) 5 culturas que só aparecem em 2025, 27 casos de área sem valor, 152 saltos de área e 16 valores por hectare atípicos;
- valida que o Total de cada município fecha com a soma das culturas (1.420 de 1.420 casos) e que o percentual do IBGE bate com o recálculo (0 divergências).

O detalhe completo, com números, está na aba `log_tratamento` do Excel.

### Reproduzir

```bash
pip install -r requirements.txt
python src/tratamento_pam.py data/raw/tabela5457_2016-2020.xlsx data/raw/tabela5457_2021-2025.xlsx --saida data/tratado --prefixo Culturas_Para_2016-2025
```

## Limitações

- Valores em **reais correntes** (nominais), sem descontar a inflação. O crescimento real é menor que 3,9×.
- 2025 é resultado **preliminar** do IBGE.
- O total do município não é divulgado em 10 casos (Marituba, e Belém e Benevides em 2016). Ficam nulos, sem estimativa.
- Gergelim, cupuaçu, acerola, graviola e milho verde só têm dado a partir de 2025 (quebra de série): não comparar com os anos anteriores.
- O valor em 2020 sobe 44% com a área +11%: a base não traz preços, então a causa (commodities, câmbio) é hipótese.
- A coluna `grupo` (grãos, frutas, perenes comerciais etc.) é uma classificação analítica deste projeto, não do IBGE.

## Fonte

IBGE, Produção Agrícola Municipal, tabela 5457 (SIDRA): área plantada ou destinada à colheita, percentual do total geral e valor da produção, por município do Pará.
