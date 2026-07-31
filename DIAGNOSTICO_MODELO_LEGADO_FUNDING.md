# Diagnóstico do modelo legado de funding

> **Classificação oficial:** este relatório analisa exclusivamente o arquivo
> legado `Funding Remo.xlsm`. O arquivo serve para compreender e reconciliar o
> modelo antigo de funding, mas não é fonte de dados operacional e nunca deve
> ser importado, espelhado ou sincronizado com o PostgreSQL. As propostas de
> importação registradas historicamente neste documento não orientam o esquema
> operacional. Esse esquema dependerá do diagnóstico separado do arquivo
> Cadastro de Clientes.

Data do diagnóstico: 27/07/2026  
Reclassificação arquitetural: 30/07/2026  
Escopo: estudo técnico do modelo legado, sem implementação.

## 1. Método e garantias

- Foram lidos integralmente `PLANO_SISTEMA_FUNDING_REMO.md`, `CLAUDE.md` e `README.md`.
- O arquivo original `data/input/Funding Remo.xlsm` não foi aberto pela ferramenta de análise.
- A análise foi feita exclusivamente em uma cópia binária temporária com nome único.
- O workbook foi aberto sem salvar, reparar ou recalcular.
- Macros não foram executadas.
- Nenhum valor foi escrito no Supabase; não houve conexão com o Supabase.
- Nenhuma migration, tabela, endpoint, tela ou código definitivo de importação foi criado.
- Exemplos de linhas foram inspecionados com dados pessoais mascarados.
- Valores monetários foram classificados com `Decimal`; não houve cálculo monetário com `float`.

Limitação importante: o workbook está em modo de cálculo manual. `openpyxl` lê fórmulas e valores em cache, mas não calcula fórmulas. Portanto, um cache vazio pode significar fórmula que devolve vazio, cache não atualizado ou ausência de cálculo anterior. Essa contagem não equivale, sozinha, a fórmula defeituosa.

## 2. Inventário do arquivo

| Item | Resultado |
|---|---|
| Arquivo original | `data/input/Funding Remo.xlsm` |
| Cópia analisada | `Funding_Remo_analysis_copy.xlsm` |
| Tamanho | 28.975.888 bytes |
| Última modificação preservada na cópia | 21/07/2026 19:42:34 |
| SHA-256 da cópia | `552ec0d5a936b61786e222d25aa6e37bab26c60c1d505bc2139f7034c4ae323e` |
| Macros | Sim; `xl/vbaProject.bin`, 56.832 bytes |
| Abas | 19 |
| Visíveis | 19 |
| Ocultas | 0 |
| Muito ocultas | 0 |
| Tabelas estruturadas do Excel | 0 |
| Fórmulas | 1.800.584 |
| Fórmulas com cache vazio | 1.023.377 |
| Modo de cálculo | Manual |
| Conexões detectáveis | 10 registros de conexão |
| Vínculos externos com outros arquivos | 0 partes de external link e 0 fórmulas com referência externa |
| Fórmulas contendo `#REF!` | 0 |
| Células com erro | 83.919 |

Erros encontrados:

| Erro | Quantidade |
|---|---:|
| `#VALUE!` | 83.576 |
| `#N/A` | 223 |
| `#DIV/0!` | 120 |
| `#REF!` | 0 |

As dez conexões possuem nomes relacionados a “Cadastro de Clientes” e referências às áreas `BCLI_CADASTRO` e `DFEN_CONTRATO`. Não foram encontrados targets externos de arquivo no pacote XLSM. Isso indica metadados de consulta/conexão embutidos, mas não prova que estejam ativos ou atualizados.

Nomes definidos:

- cinco nomes locais ocultos `_FilterDatabase`, nas abas `APURARECEITA`, `APURAVENDAS`, `ECON_AMORTIZACOES`, `ECON_EMPRESTIMOS` e `FLUXO_INVESTIDOR(A)`;
- um nome global `A`, apontando para `ECON_AMORTIZACOES!$A$3`.

## 3. Inventário completo das 19 abas

As linhas “de dados” abaixo são aproximações estruturais. Em abas preenchidas previamente com fórmulas, a dimensão física é maior que a quantidade de registros com valores em cache.

| # | Aba | Estado | Dimensão física | Cabeçalho provável | Linhas não vazias após cabeçalho | Fórmulas | Erros | Finalidade provável |
|---:|---|---|---|---:|---:|---:|---:|---|
| 1 | `BCLI_CADASTRO` | visível | `A1:Q1002` | 1 | 1.000 | 10.090 | 19 | cadastro e auxiliares de cliente |
| 2 | `MÊS_ANIVERSÁRIO` | visível | `A1:AF189` | 11, layout misto | 178 | 374 | 1 | relatório de aniversariantes |
| 3 | `DFEN_CONTRATO` | visível | `A1:X3002` | 1 | 3.001 | 6.001 | 0 | base de contratos |
| 4 | `ECON_EMPRESTIMOS` | visível | `A1:AZ3001` | 3 | 2.997 | 89.910 | 22 | empréstimos e métricas por contrato |
| 5 | `ECON_AMORTIZACOES` | visível | `A1:BA30571` | 3 | 30.567 | 1.222.679 | 83.470 | parcelas, recebimentos e rateio |
| 6 | `VALORUNICOS` | visível | `A1:B153` | 1 | 151 | 0 | 0 | lista auxiliar de situações/CPFs |
| 7 | `MOTRIZ` | visível | `A1:AO192` | layout múltiplo | 182 | 5.127 | 1 | parâmetros, faixas e matriz de KPI |
| 8 | `PROSPECT` | visível | `B1:L50` | sem cabeçalho tabular único | 8 estruturas detectadas | 0 | 0 | cadastro/formulário de prospect |
| 9 | `CAD_INV` | visível | `B1:R50` | 7, layout misto | 43 | 96 | 0 | cadastro e condições de investidores/aportes |
| 10 | `DT_DY` | visível | `B1:AG50` | 6, layout matriz | 44 | 697 | 0 | cronograma de dividend yield/remuneração |
| 11 | `APURAVENDAS` | visível | `A1:Y5001` | 6 | 4.994 | 79.959 | 7 | apuração de vendas e partes do funding |
| 12 | `APURARECEITA` | visível | `A1:AA20001` | 6 | 19.994 | 379.862 | 275 | apuração de recebimentos |
| 13 | `REL_SAFRA` | visível | `A1:S99` | 6 | 91 | 1.629 | 11 | relatório mensal de safra |
| 14 | `REL_RECEITA` | visível | `A1:AA99` | 6 | 91 | 2.357 | 113 | relatório mensal de receita |
| 15 | `FUNDING` | visível | `A1:Q55` | 6 | 34 | 510 | 0 | consolidação por investidor |
| 16 | `RATING` | visível | `A1:R23` | 6 | 11 | 138 | 0 | faixas de risco e PDD |
| 17 | `FLUXO_INVESTIDOR(A)` | visível | `A1:X96` | matriz por blocos | 81 | 1.071 | 0 | fluxo mensal por investidor |
| 18 | `TESOURARIA_BCOS` | visível | `A1:N33` | 6 | 17 | 84 | 0 | posição de capital e tesouraria |
| 19 | `KPI's` | visível | `B1:N11` | painel gráfico | 1 célula textual | 0 | 0 | dashboard baseado em `MOTRIZ` |

### 3.1 `BCLI_CADASTRO`

- Colunas exatas: `COD_CLIENTE`, `CPF_CLIENTE`, `NOME_CLIENTE`, `DT_NASC`, `ANIVERSARIANTES`, `IDADE`, `RATING`, `MÊS`, `NOME`, `CPF`, coluna K sem nome, `CPF`, `NOME`, `DATA`, `MÊS`, `REFERÊNCIA`, `VALIDAÇÃO`.
- Estrutura inicial mascarada: código, CPF, nome e nascimento manuais; datas, idade, rating e auxiliares calculados.
- Manuais principais: A:D e L.
- Calculadas: E:J e M:Q.
- Tipos: identificadores e datas-fonte como texto; datas derivadas, números, booleanos e texto nas auxiliares.
- Chaves candidatas: CPF é a melhor chave natural; `COD_CLIENTE` não é único na própria aba.
- Fórmulas relevantes: aniversário usa o ano de `TODAY()`; rating vem de `ECON_EMPRESTIMOS`; validação compara mês calculado com referência.
- Riscos: 422 linhas-fonte representam 189 CPFs e 281 códigos; há repetição de clientes/códigos, cinco datas de nascimento não parseáveis e 19 erros de fórmula.

### 3.2 `MÊS_ANIVERSÁRIO`

- Colunas/áreas detectadas: `NOME DO CLIENTE`, `DIA MÊS`, áreas C:L sem rótulo e três colunas de `VLOOKUP` em M:O; a dimensão vai até AF.
- Estrutura: relatório formatado, não base normalizada.
- Tipos: texto, data, fórmulas de busca e linhas de total.
- Relacionamento provável: deriva de `BCLI_CADASTRO`.
- Risco: cabeçalho em múltiplas linhas; não deve ser importada como fonte primária.

### 3.3 `DFEN_CONTRATO`

- Colunas exatas: `COD_CLIENTE`, `COD_CONTRATO`, `NUM_CPF`, `COD_ORGAO`, `COD_SUBORGAO`, `DATA_LIBERACAO`, `DT_INCLUSAO`, `DT_OPERACAO`, `VCTO_PRIM_PARC`, `BANCO_CREDITO`, `APROVADO`, `FORMA_PAGTO`, `TIPO_CLIENTE`, `Soma de PRAZO`, `Soma de IOF`, `Soma de PRINCIPAL`, `Soma de PMT`, `Soma de VAL_REFIN`, `Soma de VL_DISPONIVEL`, `Soma de TC`, `Soma de VL_FINANCIADO`, `Soma de VL_LIBERADO`, `MÊS_OPERAÇÃO`, `ATIVADO`.
- Manuais: A:V.
- Calculadas: W e X.
- Tipos: chaves e datas armazenadas como texto; valores numéricos; prazo com tipo misto.
- Chave candidata: `COD_CONTRATO`, 1.177 valores distintos em 1.177 registros.
- Relações: cliente por CPF/código; contrato para empréstimo e amortização.
- Fórmulas: W normaliza `DT_OPERACAO` para primeiro dia do mês; X converte presença de `APROVADO` em 0/1.
- Riscos: cinco `DATA_LIBERACAO` não parseáveis; datas-fonte não são tipos Excel de data.

### 3.4 `ECON_EMPRESTIMOS`

- Colunas exatas: `CONTROLE`, `COD_CLIENTE`, `NUM_CPF`, `COD_CONTRATO`, `DT_OPERACAO`, `PRAZO_PGTO`, `VENCIMENTO1`, `COD_ORGAO`, `COD_SUBORGAO`, `CREFISA`, `Soma de VL_DISPONIVEL`, `Soma de VL_FINACIADO`, `Soma de VL_LIBERADO`, `Soma de VL_PRINCIPAL`, `Soma de VL_REFIN`, `Soma de TC`, `Soma de IOF`, `Soma de PMT`, `Soma de TAXA_CET_AM`, `Soma de TAXA_JUROS`, `Soma de TAXA_TIR`, `MÊS OPERACAO`, `NOME _CLIENTE`, `OPERADOR`, `PROJ.TTL`, `PROJ.SAFRA`, `RECEBIDO`, `VALOR REFIN`, `A VENCER`, `VENCIDO`, `DESCONTO`, `PREJ. LÍQUIDO`, `PREJ. BRUTO`, `ADM FUNDING`, `TAXA A.A.`, `VALOR ACUM.`, `SITUAÇÃO`, `ATRASO_CTR`, `ATRASO_CPF`, `RATING`, `ANO`, `X= (VP * PRZ)`, `TX * X`, `TxEfetiva * X`, `X = VPCurva * Prz)`, `TxEfetiva * X`, `INV1`, `INV2`, `INV3`, `INV4`, `ctro`, `CPF`.
- Manuais/fonte: A:U.
- Calculadas: V:AZ.
- Tipos: chaves texto, datas, inteiros, valores monetários e percentuais; sete colunas apresentam tipos mistos.
- Chave candidata: `COD_CONTRATO`, único entre os 1.158 registros com contrato.
- Fórmulas: projeção total = prazo × PMT; recebido, a vencer, vencido, desconto e prejuízo são agregados de `ECON_AMORTIZACOES`; atraso usa máximo por contrato/CPF; rating usa faixas de `MOTRIZ`; `INV1` a `INV4` vêm de `APURAVENDAS`.
- Riscos: três contratos não existem em `DFEN_CONTRATO`; 22 células de erro; ortografia `VL_FINACIADO`; dependência de `TODAY()` e de posições fixas em `MOTRIZ`.

### 3.5 `ECON_AMORTIZACOES`

- Colunas exatas: `CHAVE 2`, `CHAVE`, `COD_CONTRATO`, `NUM_CPF`, `NOME COMPLETO`, `BOL_ANTECIP`, `COD_PARCELA`, `STATUS_PARC`, `VENCIMENTO`, `DT_BAIXATOTAL`, `Soma de VAL_PARCELA`, `Soma de VAL_PGTO`, `Soma de DESCONTO_CONC`, `Soma de VAL_AMTZ_PRINC`, `MÊS_VENCIMENTO`, `MÊS_PGTO`, `OP.FIN`, `TX_PAC`, `PMT30-30`, `PRINCIPAL`, `IOF`, `JUROS`, `PREJUÍZO`, `CHAVEPROTOCOLO`, `ATRASO_PARC`, `ATRASO CPF`, `RATING`, `SEM USO`, `DTOPERAÇAO`, coluna AD sem nome, `INV1_PROV`, `INV1_PROV`, `DESC. JUROS`, `JUR_REAL`, `PRINC_REAL`, `OPERADOR`, `INV2_PROV`, `INV2_PROV`, `DESC. JUROS`, `JUR_REAL`, `PRINC_REAL`, `OPERADOR`, `INV3_PROV`, `INV3_PROV`, `DESC. JUROS`, `JUR_REAL`, `PRINC_REAL`, `OPERADOR`, `INV4_PROV`, `INV4_PROV`, `DESC. JUROS`, `JUR_REAL`, `PRINC_REAL`.
- Fonte/manual: B:N.
- Calculadas: A e O:BA.
- Tipos: contrato/CPF texto; parcela predominantemente numérica; datas; dinheiro; status; fórmulas.
- Identificador candidato: a composição contrato + parcela é mais plausível que `COD_PARCELA` isolado. `COD_PARCELA` tem somente 67 valores distintos.
- Fórmulas: PMT e principal teórico; juros = pago − principal − IOF − desconto; atraso aberto vencido = `TODAY() - VENCIMENTO`; rating por maior atraso do CPF; rateio proporcional para até quatro investidores.
- Riscos: 12 registros referenciam contratos ausentes; 15 CPFs inválidos; três vencimentos textuais; 877 valores textuais em `DT_BAIXATOTAL`; 83.470 erros; cabeçalhos duplicados; 15 fórmulas em `AW` seguem o padrão de `AU`, divergindo do restante de `INV4_PROV` e sugerindo cópia incorreta.

### 3.6 `VALORUNICOS`

- Colunas exatas: `SITUAÇÃO`, `ABERTO`.
- Manual; texto.
- Finalidade provável: lista auxiliar usada pelo relatório de rating.
- Risco: mistura rótulos de situação e identificadores; não é dimensão confiável sem regra explícita.

### 3.7 `MOTRIZ`

- Áreas/rótulos exatos detectados: `COD`, `BANCO`, `TIPO CONTA`, `RATING`, `ATRASO`, `PDD`, `USUÁRIOS`, `COD`, `ANO`, `TITULAR`, `PRINCIPAL`, `JUROS CAPITAL`, `JUROS REMO`, `IOF`, `STATUS`, `PLR DE JUROS`, duas colunas sem rótulo, `RATING MENSAL`, `RATING (BC)`, `PARTICIPAÇAO`, referência `RATING!L6`, `PDD`, `KPI's`, `ANO`, `TIR`, `ROI`, `# CONTR`, `$ PRINCIPAL`, `$ Vencidos`, `% Inad.`, `$ Prej.`, `VL X VP`, `PRAZO`, `à Vencer`, `ACUMULADO`.
- Estrutura: diversas tabelas de parâmetros e séries para gráficos na mesma aba.
- Manual: faixas, status e parâmetros.
- Calculado: calendário mensal e séries de KPI.
- Relações: `RATING`, `REL_SAFRA`, `REL_RECEITA`, `FUNDING` e painel `KPI's`.
- Riscos: 156 valores monetários aparecem como texto na matriz histórica; uma célula com erro; nove linhas vazias internas; endereços absolutos funcionam como configuração implícita.

### 3.8 `PROSPECT`

- Não há cabeçalho tabular único comprovável em B:L; a aba se comporta como formulário/cadastro formatado.
- A detecção encontrou dados de identidade e contato, todos omitidos deste relatório.
- Manual; tipos texto, documento, contato, marcadores e datas.
- Relação: `CAD_INV!D` busca a segunda coluna de `PROSPECT!B:F` usando `CAD_INV!B`.
- Risco: ausência de chave e cabeçalho técnico explícitos; contém PII e não deve ser importada por posição sem mapeamento aprovado.

### 3.9 `CAD_INV`

- Colunas/áreas exatas detectadas na linha estrutural: quatro colunas iniciais sem rótulo técnico, `DATA`, `VALOR - R$`, `DATA I`, `DATA F`, `MÊS`, `PRINC`, coluna K sem rótulo, `DIA`, `BANCO`, `AGENCIA`, `CONTA`, `TIPO`, `CHAVE PIX`.
- Estrutura inicial mascarada: referência de prospect, nome de investidor, valor, vigência e dados bancários; nenhum dado pessoal foi reproduzido.
- Manuais: B:C, E:G, parte de H e L:Q.
- Calculadas: D, I e J; uma célula de H também é fórmula.
- Tipos: texto, datas, valores e fórmulas.
- Chave candidata: identidade do investidor em C; há nove valores distintos.
- Fórmulas: D busca em `PROSPECT`; I calcula remuneração mensal (`F × 1,5%` em oito linhas e `F × 5%` em uma); J distribui principal por duração aproximada em meses; uma vigência final usa início + 16 meses.
- Riscos: taxa embutida em fórmula; quantidade pequena de linhas ativas dentro de área pré-formatada; nenhuma chave técnica de aporte; PII bancária.

### 3.10 `DT_DY`

- Áreas exatas: `NOME COMPLETO`, `INVESTIDOR(A)`, `DATA DE PAGAMENTO DA REMUNERAÇÃO MENSAL`, calendário em E:AB sem rótulos individuais, `VALOR RECEBIDO`, coluna AD sem rótulo, `QUITAÇÃO`, coluna AF sem rótulo, `OBSERVAÇÃO`.
- Estrutura: matriz temporal, não base linha-a-linha.
- Manuais: investidor, data inicial, valor recebido, quitação e observação.
- Calculadas: meses subsequentes e totalização.
- Fórmulas: datas mensais sucessivas; total recebido pela contagem de períodos × valor.
- Risco: uma linha de total interna; regra de quitação não comprovada por fórmula.

### 3.11 `APURAVENDAS`

- Colunas exatas: coluna A sem nome, `CONTR`, `NOME COMPLETO`, `DT VENDA`, `R$ PARCELA`, `TX JUROS (a.m.)`, `R$ PRINCIPAL`, `R$ LIBERADO`, `R$ FIN`, `PROJETADO`, `REF.`, `OPERADOR CAIXA`, `PARTE 1`, coluna N sem nome, `PARTE 2`, coluna P sem nome, `PARTE 3`, coluna R sem nome, `PARTE 4`, coluna T sem nome, `True`, `VALID?`, `RESPONSÁVEL`, `R$ REFIN/RENEG`, `PRAZO`.
- Calculadas: A:L, T:U, X:Y e auxiliares.
- Manuais: pares M:N, O:P, Q:R e S:T parcialmente preenchidos representam investidor e valor; V:W são validação/responsável.
- Tipos: contrato, texto, data, dinheiro, percentual, booleano.
- Chave candidata: `CONTR`; vem de `ECON_EMPRESTIMOS`.
- Fórmulas: dados do contrato são buscados em `ECON_EMPRESTIMOS`/`DFEN_CONTRATO`; residual da quarta parte = valor liberado − partes anteriores; U valida se as quatro partes somam o valor liberado.
- Riscos: limite rígido de quatro partes; sete erros; a fórmula de contagem em `FUNDING` contém referência incomum `APURAVENDAS!Q:NP`, possivelmente erro de intervalo.

### 3.12 `APURARECEITA`

- Colunas exatas: coluna A sem nome, `CONTR`, `NOME COMPLETO`, `No PARC`, `DT VENC`, `DT PGTO`, `$ PMT`, `$ PAGO`, `STATUS`, `OBSERVAÇÃO`, `OPERADOR(A) FINANCEIRO`, `$ PRINCIPAL`, `$ JUROS`, `$ I.O.F`, `$ BX PREJUÍZO`, `$ DESC. CONC`, `$ TOTAL APURADO`, `REF. PGTO`, `INVESTIDOR(A) PRINCIPAL`, `ENTRADA CAIXA`, três colunas U:W sem nome, `SAÍDA CAIXA`.
- Calculadas: A:S.
- Manuais/prováveis: T:X, especialmente entrada e saída de caixa.
- Tipos: contrato, parcela, datas, status, dinheiro e texto.
- Relação: espelha `ECON_AMORTIZACOES`; contrato é copiado diretamente.
- Fórmula central: se principal + juros + IOF = pago, total apurado = pago; caso contrário, total = principal + juros + IOF − prejuízo − desconto.
- Riscos: não é fonte independente; 275 erros; 877 sentinelas textuais de pagamento são herdadas; o `VLOOKUP` de `REF. PGTO` usa índice 10 no intervalo A:O, portanto retorna a coluna J, não O — deve ser confirmado pela REMO.

### 3.13 `REL_SAFRA`

- Colunas exatas: coluna A sem nome, `MÊS`, coluna C sem nome, `∑ CONTR`, `∑ NOVOS`, `μ (simples) PRAZO`, `TMP (JUROS)`, `$ VP`, `$ VL`, `$ IOF`, `$ PROJ. TTL`, `$ PROJ. SAFRA`, `$ RECBTO NOMINAL`, `$ RECBTO REAL`, `$ REFIN/ DESCAPITALIZAÇÃO`, `$ À VENCER`, `$ VENCIDO`, `$ PREJ. LIQ`, `% INAD.%`.
- Calculada; relatório agregado por mês.
- Risco: 11 erros; não deve ser importada como fato primário.

### 3.14 `REL_RECEITA`

- Colunas exatas: coluna A sem nome, `MÊS`, coluna C sem nome, `TMP (TAXA PACTUADA)`, `TMP (TIR)`, `TMP (CET CURVA)`, `$ VP`, `$ VL`, `% VL x VP`, `$ IOF`, `$ PROJ. TTL`, `% PROJ. TOTAL`, `$ PROJ. SAFRA`, `% PROJ. SAFRA`, `$ RECBTO NOMINAL`, `% RECBTO NOMINAL`, `$ RECBTO REAL`, `% RECBTO REAL`, `$ REFIN/ DESCAPITALIZAÇÃO`, `$ À VENCER`, `% A VENCER`, `$ VENCIDO`, `% VENCIDO`, `$ PREJ. LIQ`, `% VENCIDO`, `% INAD. %`, `% ROI`.
- Calculada; relatório agregado.
- Risco: 113 erros e dois rótulos `% VENCIDO`; validar semântica de Y e W.

### 3.15 `FUNDING`

- Colunas exatas: coluna A sem nome, `INVESTIDOR(A)`, `KICKOFF (REF.)`, `% RETURN`, `∑ CONTR`, `μ (simples) PRAZO`, `TMP (JUROS)`, `$ VP`, `$ VL`, `$ PROJ. TTL`, `$ PROJ. SAFRA`, `$ RECBTO NOMINAL`, `$ RECBTO REAL`, `$ À VENCER`, `$ VENCIDO`, `$ PREJ. LIQ`, `% INAD. %`.
- B e D:Q são calculadas; C é aparentemente manual/referencial.
- Relações: investidor vem de `MOTRIZ`; alocações vêm dos quatro pares de `APURAVENDAS`; recebimentos vêm de `ECON_AMORTIZACOES`.
- Fórmulas: retorno = recebimento real / valor liberado; inadimplência = vencido / projetado da safra; demais métricas são `SUMIFS` por investidor nas quatro posições.
- Riscos: 16 nomes calculados não encontram correspondência direta na pequena base ativa de `CAD_INV`; referência `Q:NP` na contagem; dependência rígida de quatro partes e de `TODAY()`.

### 3.16 `RATING`

- Colunas exatas: coluna A sem nome, `RATING (BC)`, `DESCRIÇÃO`, `PDD`, `TMP (JUROS)`, `μ (média) PMT`, `CLIENTE`, coluna H sem nome, `CONTRATO`, coluna J sem nome, `PRINCIPAL`, coluna L sem nome, `RECEBIDO`, coluna N sem nome, `PENDENTE`, coluna P sem nome, `PDD`, `%`.
- Manuais: faixas/rótulos B:D.
- Calculadas: E:R.
- Fórmulas: PDD em Q = principal K × percentual D; demais pares valor/percentual agregam clientes, contratos, principal, recebido e pendente por rating.
- Risco: posições fixas de faixas; uma linha de total e uma linha vazia interna.

### 3.17 `FLUXO_INVESTIDOR(A)`

- Não há cabeçalho tabular único. Cada investidor ocupa um bloco; B identifica o investidor, C contém principal e D:R representam meses/séries. A dimensão chega a X.
- Calculada a partir de `CAD_INV`, `ECON_EMPRESTIMOS` e das quatro posições de investidor.
- Fórmulas: principal por `VLOOKUP`; calendário mensal; captação/uso por `SUMIFS`; retorno acumulado dividido pelo principal; nove blocos usam remuneração mensal com fator fixo de 1,5%.
- Riscos: layout por blocos, nove linhas vazias internas, taxa fixa na fórmula e forte dependência de posição.

### 3.18 `TESOURARIA_BCOS`

- Colunas exatas: coluna A sem nome, `INVESTIDORES`, `DATA INICIO`, `DATA FIM`, `STATUS`, `VALOR PRINCIPAL`, `SALDO PRINCIPAL`, `CAPITAL ACUMULADO`, `JUROS ACUMULADO`, `CAPITAL DEVOLVIDO`, `PJR`, `CAPITAL REINVESTIDO`, `JUROS REINVESTIDO`, `OBSERVAÇÃO`.
- Calculadas: B:C, F:I e K; J, L, M têm células manuais e totalizadores.
- Manuais: D:E, J, L:N.
- Fórmulas: principal e início vêm de `CAD_INV`; capital/juros acumulados somam rateios das quatro posições; PJR aplica faixas `MOTRIZ!P:Q`.
- Riscos: um investidor sem correspondência em `CAD_INV`; quatro linhas vazias internas; quatro valores `time` na coluna de data inicial; a fórmula de saldo subtrai a primeira parte e soma as partes 2–4, exigindo validação do sinal.

### 3.19 `KPI's`

- Não é uma base de células. A aba possui um drawing com 20 âncoras: 11 gráficos, 8 shapes e 1 imagem.
- Os gráficos leem exclusivamente séries da aba `MOTRIZ`.
- Indicadores identificados pelas referências/títulos: rating, TIR, ROI, contratos × principal, inadimplência, principal × prejuízo, liberado × principal, prazo, a vencer, investidores e acumulado.
- Risco: indicadores não têm fórmula própria na aba; sua definição depende das fórmulas e posições de `MOTRIZ`, `REL_SAFRA` e `REL_RECEITA`.

## 4. Dicionário preliminar de dados

| Entidade preliminar | Fonte principal | Chave candidata | Observação |
|---|---|---|---|
| Cliente | `BCLI_CADASTRO` A:D | CPF normalizado; código como chave de origem | há várias linhas por CPF/código |
| Contrato | `DFEN_CONTRATO` | `COD_CONTRATO` | único na base |
| Empréstimo | `ECON_EMPRESTIMOS` A:U | `COD_CONTRATO` | três contratos fora de DFEN |
| Parcela | `ECON_AMORTIZACOES` B:N | `(COD_CONTRATO, COD_PARCELA)`; confirmar `CHAVE` | parcela isolada não é única |
| Prospect | `PROSPECT` | não comprovada | contém PII |
| Investidor importado | `CAD_INV` | identidade normalizada em C; precisa de ID técnico | nove registros ativos |
| Aporte | `CAD_INV` | inexistente no Excel | valor/vigência existem, mas não há ID estável de aporte |
| Alocação em contrato | `APURAVENDAS` M:T | contrato + posição 1..4 | modelar como linhas, não quatro colunas |
| Recebimento | `ECON_AMORTIZACOES` e `APURARECEITA` | parcela + evento; confirmar | APURARECEITA é derivada |
| Rating/PDD | `MOTRIZ` e `RATING` | código/faixa de rating | regras por posição |
| Tesouraria | `TESOURARIA_BCOS` | investidor + evento/data | mistura fatos manuais e saldos calculados |

## 5. Relacionamentos comprovados

“Duplicidade no destino” pode ser esperada em relações 1:N; não é automaticamente erro.

| Relação | Origem → destino | Valores distintos relacionados | Registros relacionados | Órfãos no destino | Duplicados origem | Duplicados destino | Confiança |
|---|---|---:|---:|---:|---:|---:|---|
| Cliente → contrato por CPF | `BCLI_CADASTRO.CPF_CLIENTE` → `DFEN_CONTRATO.NUM_CPF` | 189 | 1.177 | 0 | 233 | 988 | alta |
| Cliente → contrato por código | `BCLI_CADASTRO.COD_CLIENTE` → `DFEN_CONTRATO.COD_CLIENTE` | 281 | 1.177 | 0 | 141 | 896 | alta, mas origem não única |
| Contrato → empréstimo | `DFEN_CONTRATO.COD_CONTRATO` → `ECON_EMPRESTIMOS.COD_CONTRATO` | 1.155 | 1.155 | 3 | 0 | 0 | alta |
| Contrato → amortização | `DFEN_CONTRATO.COD_CONTRATO` → `ECON_AMORTIZACOES.COD_CONTRATO` | 1.121 | 9.784 | 12 | 0 | 8.674 | alta |
| Contrato → receita | `DFEN_CONTRATO.COD_CONTRATO` → `APURARECEITA.CONTR` | 1.121 | 9.784 | 12 | 0 | 8.674 | alta estrutural, não independente |
| Investidor → consolidação | `CAD_INV.C` → `FUNDING.INVESTIDOR(A)` | 9 | 9 | 16 | 0 | 0 | média |
| Investidor → alocação | `CAD_INV.C` → `APURAVENDAS.PARTE 1..4` | 3 | 82 | 0 | 0 | 79 | média/alta |
| Investidor → tesouraria | `CAD_INV.C` → `TESOURARIA_BCOS.INVESTIDORES` | 9 | 9 | 1 | 0 | 0 | média |

Não comprovado:

- **aporte → contrato**: o Excel comprova investidor e valor alocado por contrato, mas não oferece um identificador de aporte que permita ligar uma alocação a um aporte específico;
- `FUNDING` e `TESOURARIA_BCOS` usam nome do investidor como junção, o que é frágil.

## 6. Regras atuais do funding

1. **Cadastro de investidor**: `CAD_INV` referencia `PROSPECT` por busca em B:F. A identidade usada nas demais abas aparece em C.
2. **Aporte**: `CAD_INV.F` armazena valor; `G/H` representam início/fim. Não existe ID de aporte, nem ficou provado se uma pessoa pode ter múltiplos aportes simultâneos.
3. **Taxas**: `CAD_INV.I` usa taxa fixa na fórmula: oito registros a 1,5% e um a 5%. Não se deve generalizar essas taxas sem confirmação.
4. **Vigência**: uma fórmula de `DATA F` soma 16 meses ao início; outras datas finais são manuais. Não há regra única comprovada.
5. **Capital utilizado/alocação**: `APURAVENDAS` usa quatro pares investidor/valor: M:N, O:P, Q:R, S:T.
6. **Limite atual de partes**: quatro. O restante da arquitetura do workbook repete exatamente quatro posições.
7. **Validação do rateio inicial**: U compara a soma N+P+R+T com o valor liberado H.
8. **Rateio de recebimento**: para cada uma das quatro partes, `ECON_AMORTIZACOES` calcula proporção `valor da parte / valor liberado` e aplica a principal, juros e desconto.
9. **Desconto**: juros reais têm piso zero; quando desconto supera juros provisionados, o excedente reduz principal real.
10. **Remuneração/dividend yield**: `FLUXO_INVESTIDOR(A)` calcula fluxos mensais, retorno acumulado/principal e usa 1,5% fixo em nove blocos. `FUNDING.% RETURN` usa recebimento real / valor liberado.
11. **PJR**: `TESOURARIA_BCOS.K` aplica faixas de `MOTRIZ.P:Q` sobre a razão juros acumulados/principal e multiplica os juros pela alíquota da faixa.
12. **Reinvestimento e devolução**: existem campos manuais `CAPITAL DEVOLVIDO`, `CAPITAL REINVESTIDO` e `JUROS REINVESTIDO`; apenas os totais são fórmulas. A política de evento não está comprovada.
13. **Liquidação/antecipação**: `BOL_ANTECIP` é levado a `APURARECEITA.OBSERVAÇÃO`; status e datas distinguem parcelas. A regra jurídica/financeira de quitação antecipada não está explícita.
14. **Inadimplência**: parcela aberta e vencida recebe dias `TODAY() - vencimento`; determinados status recebem atraso convencional de 365 dias. O maior atraso do CPF determina rating.
15. **PDD**: `RATING.Q = RATING.K × RATING.D`, isto é, principal por rating × percentual da faixa.
16. **Prejuízo**: `ECON_AMORTIZACOES.W` reconhece prejuízo por status referenciado em `MOTRIZ`; `ECON_EMPRESTIMOS` consolida prejuízo líquido e bruto.
17. **Tesouraria**: saldo, capital e juros acumulados dependem das quatro posições de alocação; devolução e reinvestimento são registros manuais.
18. **Arredondamento**: não foi encontrada uma política central de `ROUND`. As fórmulas operam com precisão binária/célula e a apresentação visual pode ocultar frações. A Fase 1 precisa definir `Decimal` e arredondamento explícito.
19. **KPI**: painel composto por 11 gráficos alimentados por `MOTRIZ`; não há cálculo próprio no dashboard.

## 7. Qualidade dos dados

### 7.1 Contagens refinadas

| Verificação | Resultado |
|---|---:|
| CPFs inválidos em `BCLI_CADASTRO` | 0 de 422 |
| CPFs inválidos em `DFEN_CONTRATO` | 0 de 1.177 |
| CPFs inválidos em `ECON_EMPRESTIMOS` | 0 de 1.158 |
| CPFs inválidos em `ECON_AMORTIZACOES` | 15 de 9.796 |
| CPFs distintos associados a nomes divergentes entre bases | 34 |
| Contratos sem cliente por CPF | 0 |
| Contratos sem cliente por código | 0 |
| Empréstimos sem contrato DFEN | 3 |
| Parcelas/amortizações sem contrato DFEN | 12 |
| Linhas de receita sem contrato DFEN | 12, herdadas da amortização |
| Códigos de contrato ausentes nas linhas efetivas analisadas | 0 |
| Códigos de parcela ausentes nas linhas efetivas | 0 |
| Valores monetários parseáveis armazenados como texto nas colunas principais | 0 |
| Células com erro | 83.919 |
| Fórmulas com cache vazio | 1.023.377 |
| Linhas de total/subtotal detectadas | 4 |
| Colunas com tipos misturados | 70 na varredura estrutural |
| Linhas totalmente vazias dentro de áreas de dados | 23 |
| Referências externas de arquivo | 0 |
| Fórmulas quebradas com `#REF!` | 0 |
| Chaves principais com espaços/caracteres invisíveis | 0 |

Duplicidades que precisam de interpretação:

- `BCLI_CADASTRO`: 233 repetições de CPF e 141 repetições de código; isso é anormal para um cadastro canônico e requer regra de deduplicação.
- `DFEN_CONTRATO`: CPF e cliente repetem porque um cliente possui vários contratos; `COD_CONTRATO` é único.
- `ECON_AMORTIZACOES`: contrato e parcela isolada repetem porque a relação é 1:N; a chave deve ser composta.

Datas:

- cinco `DT_NASC` e cinco `DATA_LIBERACAO` não são parseáveis;
- três `VENCIMENTO` são textuais;
- `DT_BAIXATOTAL` contém 877 sentinelas textuais em vez de data; isso deve ser modelado como “sem baixa/estado”, não corrigido como data;
- quatro resultados de `TESOURARIA_BCOS.DATA INICIO` foram lidos como hora, consequência provável de busca/célula vazia formatada;
- `APURARECEITA` repete as mesmas ocorrências da amortização e não deve dobrar a contagem.

### 7.2 Fórmulas divergentes ou suspeitas

1. `FUNDING` usa `COUNTIFS(APURAVENDAS!Q:NP, ...)` em parte das fórmulas; o intervalo é incompatível com as demais posições.
2. `APURARECEITA.REF. PGTO` busca índice 10 em A:O, retornando J.
3. `TESOURARIA_BCOS.SALDO PRINCIPAL` subtrai a parte 1 e soma as partes 2–4.
4. Quinze células de `ECON_AMORTIZACOES.AW` têm fórmula do bloco anterior, diferente do padrão de `INV4_PROV`.
5. `ECON_EMPRESTIMOS.PREJ. BRUTO` usa `COD_PARCELA` como critério contra células de status de `MOTRIZ`, o que merece confirmação.

Nada foi corrigido nesta fase.

## 8. Riscos técnicos

- Cálculo manual e caches potencialmente desatualizados.
- 1,8 milhão de fórmulas; leitura e validação serão caras.
- 83.919 erros em células, concentrados em `ECON_AMORTIZACOES`.
- Ausência de tabelas estruturadas e chaves técnicas explícitas.
- Junções por nome de investidor.
- Quatro partes fixas em colunas, incompatíveis com rateio N:N escalável.
- Regras dependentes de `TODAY()`, endereços absolutos e posições de `MOTRIZ`.
- Taxas de 1,5%/5% embutidas em fórmulas.
- Dados-fonte de datas armazenados como texto.
- Cabeçalhos duplicados, vazios e layouts múltiplos.
- VBA e conexões embutidas, embora não executados.
- Recursos de validação/conditional formatting que bibliotecas podem perder caso alguém salve o XLSM; a integração deve permanecer somente leitura.
- `openpyxl` não recalcula Excel; valores derivados não podem ser tomados como atuais sem política de cache/recalculação fora do sistema.

## 9. Dúvidas para a REMO

1. Qual é a regra para escolher a linha canônica quando CPF/código se repete em `BCLI_CADASTRO`?
2. Os três empréstimos e as 12 parcelas sem contrato são válidos, históricos ou erros?
3. O que significam exatamente as 877 sentinelas de `DT_BAIXATOTAL`?
4. A taxa mensal é individual, por aporte, por investidor ou por período? Por que há 1,5% e 5%?
5. A vigência padrão é 16 meses ou livre?
6. Um investidor pode ter múltiplos aportes e taxas/vigências simultâneas?
7. Como identificar unicamente um aporte?
8. O limite de quatro investidores por contrato é regra de negócio ou limitação da planilha?
9. Qual política de arredondamento deve ser usada em rateio e remuneração?
10. Qual evento gera devolução, reinvestimento e quitação?
11. PJR incide sobre juros recebidos, acumulados ou pagos? Em qual momento?
12. Os sinais da fórmula de `SALDO PRINCIPAL` estão corretos?
13. `Q:NP` em `FUNDING` é intencional?
14. `REF. PGTO` deve retornar `DT_BAIXATOTAL`, `MÊS_PGTO` ou outro campo?
15. As 15 fórmulas divergentes de `INV4_PROV` são exceção válida?
16. Quais códigos reais correspondem aos status mantidos em `MOTRIZ.C14:C20`?
17. O atraso convencional de 365 dias para certos status é regra oficial?
18. PDD deve usar principal original, saldo atual ou exposição a vencer?
19. Os relatórios e KPI devem reproduzir o cache atual ou ser recalculados a partir dos fatos?
20. Qual é o significado distinto das duas colunas `% VENCIDO` em `REL_RECEITA`?

## 10. Proposta histórica, substituída para a importação operacional

Esta seção registra conclusões preliminares produzidas antes da separação
oficial das fontes. Nada foi implementado. Ela pode ajudar a compreender o
modelo legado de funding, mas **não deve ser usada para definir o espelho
operacional, a ordem de importação ou o mapeamento do Cadastro de Clientes**.
Essas decisões serão refeitas após
`FASE_1A_DIAGNOSTICO_CADASTRO_CLIENTES.md`.

### 10.1 Ordem recomendada de importação

1. lote de importação e metadados do arquivo;
2. `MOTRIZ` e `RATING` como parâmetros de referência versionados;
3. `PROSPECT` com proteção reforçada de PII;
4. `BCLI_CADASTRO`;
5. `DFEN_CONTRATO`;
6. `ECON_EMPRESTIMOS`;
7. `ECON_AMORTIZACOES`;
8. `CAD_INV`;
9. alocações manuais de `APURAVENDAS`;
10. eventos manuais de `APURARECEITA` e `TESOURARIA_BCOS`;
11. relatórios e KPI somente para reconciliação.

### 10.2 Tabelas espelho propostas

- `excel_import_batches`
- `excel_bcli_cadastro_rows`
- `excel_dfen_contrato_rows`
- `excel_econ_emprestimos_rows`
- `excel_econ_amortizacoes_rows`
- `excel_prospect_rows`
- `excel_cad_inv_rows`
- `excel_apuravendas_rows`
- `excel_apurareceita_rows`
- `excel_tesouraria_bcos_rows`
- `excel_parameter_rows` para `MOTRIZ`/`RATING`

Cada linha espelho deve guardar lote, aba, número de linha, chave de origem, hash do conteúdo, payload tipado e estado de validação. Não deve guardar fórmula como regra operacional definitiva.

### 10.3 Tabelas próprias do sistema propostas

- `clients`
- `contracts`
- `installments`
- `investors`
- `contributions`
- `contract_allocations`
- `cash_receipts`
- `allocation_receipts`
- `investor_ledger_entries`
- `treasury_entries`
- `rating_bands`
- `pdd_rules`
- `pjr_rules`
- `data_inconsistencies`
- `sync_runs`

As quatro partes devem virar linhas de `contract_allocations`, permitindo N investidores por contrato.

### 10.4 Mapeamento preliminar Excel → PostgreSQL

| Excel | PostgreSQL | Observação |
|---|---|---|
| códigos, CPF/CNPJ, contrato, parcela | `TEXT` | preservar zeros e formato de origem; armazenar versão normalizada separada |
| datas válidas | `DATE` | parse explícito; sentinela vai para status/observação |
| data/hora real | `TIMESTAMP WITH TIME ZONE` somente se houver hora de negócio | hoje a maioria é data |
| 0/1 e validações | `BOOLEAN` | não inferir de texto sem mapa |
| prazo/dias/parcela | `INTEGER` | após validação |
| dinheiro | `NUMERIC(14,2)` | sempre `Decimal` |
| taxas/percentuais | `NUMERIC(12,8)` | armazenar fração, por exemplo 1,5% = 0,015 |
| percentuais de apresentação | cálculo/serialização | arredondar apenas na borda |
| status/rating | `TEXT` ou FK de dimensão | mapa versionado |
| conteúdo original não parseável | `TEXT` de origem + inconsistência | nunca corrigir silenciosamente |

### 10.5 Colunas para `NUMERIC(14,2)`

- `DFEN_CONTRATO`: IOF, PRINCIPAL, PMT, VAL_REFIN, VL_DISPONIVEL, TC, VL_FINANCIADO, VL_LIBERADO.
- `ECON_EMPRESTIMOS`: K:R, Y:AG, AJ e os valores auxiliares ponderados AP/AS quando monetários.
- `ECON_AMORTIZACOES`: K:N, S:W, AE:AI, AK:AO, AQ:AU e AW:BA.
- `CAD_INV`: `VALOR - R$`, remuneração mensal e principal mensal.
- `APURAVENDAS`: E, G:J, N, P, R, T e X.
- `APURARECEITA`: G:H, L:Q, T e X.
- `REL_SAFRA`, `REL_RECEITA`, `FUNDING`: todas as colunas prefixadas por `$`.
- `TESOURARIA_BCOS`: F:M, exceto se PJR for mantido como percentual; pelo uso atual K é valor monetário.

### 10.6 Percentuais e precisão

- taxas contratuais, CET, TIR, taxa de juros, participação e retorno: `NUMERIC(12,8)`;
- PDD, PJR e faixas percentuais: `NUMERIC(9,6)`, salvo exigência regulatória maior;
- razões de KPI: `NUMERIC(12,8)`;
- nunca usar `FLOAT`, `REAL` ou `DOUBLE PRECISION` para valores financeiros.

### 10.7 Atualização, inserção e remoção lógica

1. Copiar o XLSM original para arquivo temporário único.
2. Criar lote por SHA-256 e impedir reprocessamento acidental do mesmo hash.
3. Carregar primeiro em staging/espelho dentro de transação.
4. Validar chaves, tipos, órfãos, totais e inconsistências.
5. Promover por `upsert` usando chaves estáveis e `source_row_hash`.
6. Marcar `last_seen_batch_id` em registros vistos.
7. Somente após lote completo e válido, marcar como inativos os registros ausentes (`source_active = false`, `source_valid_to`), sem exclusão física.
8. Preservar histórico e trilha de auditoria.
9. Não sobrescrever dados geridos pelo sistema com vazio ou erro do Excel.
10. Falhar o lote inteiro quando a integridade mínima não for atendida.

### 10.8 Recomendação sobre `CAD_INV`

Recomendação: **separar cadastro importado de cadastro canônico do sistema**.

- Fazer carga inicial e snapshots permanentes de `CAD_INV`.
- Manter `investors` e `contributions` próprios, ligados às linhas importadas.
- Na arquitetura corrigida, `CAD_INV` pertence somente ao legado; investidores
  e aportes canônicos do novo sistema têm o PostgreSQL Supabase como fonte da
  verdade. Nenhuma carga dessa aba está aprovada.
- A gestão nativa de novos investidores/aportes deve ser aprovada como mudança arquitetural posterior.

### 10.9 Recomendação sobre relatórios

| Aba | Recomendação |
|---|---|
| `FUNDING` | recalcular a partir de alocações/recebimentos; usar a aba como referência de reconciliação |
| `TESOURARIA_BCOS` | importar somente eventos manuais; recalcular saldos, capital, juros e PJR |
| `KPI's` | substituir por indicadores do sistema; usar os 11 gráficos atuais como referência de validação |
| `REL_SAFRA` / `REL_RECEITA` | não espelhar como fatos; recalcular e reconciliar |

## 11. Conclusão

Este diagnóstico permanece válido para compreender o funding legado, suas
fórmulas, limitações e indicadores. Ele não comprova a estrutura da fonte
operacional e não autoriza importar nenhuma de suas 19 abas. Clientes,
contratos, empréstimos e amortizações serão modelados somente após o
diagnóstico do Cadastro de Clientes. Investidores, aportes, alocações,
remunerações, PJR, reinvestimentos e tesouraria do novo sistema terão o
PostgreSQL Supabase como fonte da verdade.

Nenhuma implementação da Fase 1B foi iniciada.
