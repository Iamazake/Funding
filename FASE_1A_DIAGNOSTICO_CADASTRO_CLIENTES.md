# Fase 1A — Diagnóstico do Cadastro de Clientes

> Status: diagnóstico técnico concluído. Este documento descreve a fonte
> operacional `Cadastro de Clientes.xlsm`; não descreve o modelo legado de
> funding.
>
> A Fase 1B não foi iniciada. Nenhum reader definitivo, sincronização,
> migration ou acesso ao Supabase foi executado.

## 1. Escopo e garantias de execução

- O caminho foi obtido exclusivamente de `OPERATIONAL_EXCEL_PATH` no `.env`
  local e não foi incluído neste relatório.
- O arquivo original não foi aberto pela biblioteca de análise. Primeiro foi
  criada uma cópia temporária e somente essa cópia foi inspecionada.
- A análise foi somente leitura; não houve gravação, salvamento ou recálculo.
- Macros não foram executadas e conexões externas não foram atualizadas.
- Nenhum conteúdo de célula, senha, token, connection string ou dado pessoal
  foi persistido no repositório.
- Nenhuma operação foi feita no PostgreSQL/Supabase.
- O arquivo legado `Funding Remo.xlsm` não foi lido nesta execução.

### Identificação da fonte

| Propriedade | Resultado |
|---|---|
| Nome real | `Cadastro de Clientes.xlsm` |
| Extensão | `.xlsm` |
| Tamanho | 32.170.500 bytes |
| Modificação observada | 30/07/2026 18:03:01, horário local |
| SHA-256 | `82ac1773aedfe9d28c683be39b88e7d7d612c26ef8d5ffd17eafb6a28a006e2a` |
| Abas | 43 |
| Visíveis | 29 |
| Ocultas | 14 |
| Muito ocultas | 0 |

O hash identifica exatamente a versão analisada. Uma mudança futura no hash
deve disparar nova validação de layout antes de qualquer sincronização.

## 2. Estrutura geral do arquivo

O arquivo não é apenas um conjunto de quatro tabelas. Ele reúne:

1. bases operacionais de clientes, contratos, empréstimos e amortizações;
2. cadastros auxiliares e tabelas de domínio;
3. simuladores e cálculos financeiros;
4. geração de boletos, contratos e anexos;
5. painéis e relatórios;
6. áreas com informações de acesso e dados bancários sensíveis.

Foram encontradas 2.962.289 células com fórmula. Desse total, 1.437.259 não
possuíam resultado em cache acessível pelo leitor. Isso não significa, por si
só, fórmula inválida, mas impede que uma importação dependa de recálculo ou de
cache sempre disponível.

### Componentes do pacote XLSM

| Item | Resultado |
|---|---|
| Projeto VBA | presente, 10.634.240 bytes |
| Conexões registradas | 5 (`web_cep` e quatro variantes) |
| Links externos no pacote | nenhum target encontrado |
| Fórmulas com referência externa detectável | 0 |
| Objetos de tabela estruturada do Excel | 0 |
| Nomes definidos | 29, quase todos filtros locais; uma área de impressão |
| Partes internas do arquivo | 165 |

A presença de VBA e conexões de CEP reforça a obrigação de copiar o arquivo e
abri-lo sem macros nem atualização de links. A ausência de tabelas estruturadas
significa que o futuro reader precisará validar aba, cabeçalho e colunas
explicitamente.

## 3. Inventário das abas

As contagens abaixo representam células não vazias, inclusive fórmulas. Em
abas com fórmulas pré-preenchidas até centenas de milhares de linhas, elas não
equivalem a registros operacionais reais.

| # | Aba | Estado | Dimensão declarada | Cabeçalho | Linhas não vazias após cabeçalho | Colunas usadas | Fórmulas | Erros | Classificação técnica |
|---:|---|---|---|---:|---:|---:|---:|---:|---|
| 1 | `Imagem` | visível | `A1:M10` | 1 | 7 | 13 | 0 | 0 | apresentação/configuração |
| 2 | `CAD_USUARIOS` | visível | `A1:L35` | 1 | 25 | 12 | 0 | 0 | usuários e campos de acesso; sensível |
| 3 | `TIPO_DOCUMENTO` | oculta | `A1:B7` | 1 | 6 | 2 | 0 | 0 | domínio |
| 4 | `NACIONALIDADE` | oculta | `A1:B3` | 1 | 2 | 2 | 0 | 0 | domínio |
| 5 | `GENERO` | oculta | `A1:B3` | 1 | 2 | 2 | 0 | 0 | domínio |
| 6 | `ESTADO_CIVIL` | oculta | `A1:B7` | 1 | 6 | 2 | 0 | 0 | domínio |
| 7 | `ESCOLARIDADE` | oculta | `A1:B12` | 1 | 11 | 2 | 0 | 0 | domínio |
| 8 | `TIPO_TELEFONE` | oculta | `A1:B4` | 1 | 3 | 2 | 0 | 0 | domínio |
| 9 | `TIPO_RESIDENCIA` | oculta | `A1:B6` | 1 | 5 | 2 | 0 | 0 | domínio |
| 10 | `NATUREZA_OCUP` | oculta | `A1:B14` | 1 | 12 | 2 | 0 | 0 | domínio |
| 11 | `TIPO_COMPROVANTE` | oculta | `A1:B6` | 1 | 5 | 2 | 0 | 0 | domínio |
| 12 | `TIPO_CONTA` | oculta | `A1:B5` | 1 | 4 | 2 | 0 | 0 | domínio |
| 13 | `CAD_ORGAO_SUBORGAO` | oculta | `A1:L1` | 1 | 0 | 12 | 0 | 0 | estrutura vazia nesta versão |
| 14 | `TIPO_PRODUTO` | oculta | `A1:B4` | 1 | 3 | 2 | 0 | 0 | domínio |
| 15 | `TIPO_CLIENTE` | oculta | `A1:E22` | 1 | 4 | 3 | 0 | 0 | domínio |
| 16 | `ORGAO_EMISSOR` | visível | `A1:P28` | 1 | 27 | 16 | 0 | 0 | domínio composto |
| 17 | `PRODUTO_MODAL` | visível | `A1:Z148` | 1 | 147 | 22 | 772 | 0 | regras/produtos |
| 18 | `REGRAS_PV` | visível | `A1:BI1048266` | 1 | 1.048.265 | 49 | 1.051.110 | 0 | regra calculada; alcance inflado |
| 19 | `SIMULACAO_VL_LIBERADO` | oculta | `A1:AN101` | 20 | 81 | 35 | 2.311 | 1.477 | simulador |
| 20 | `Cadastro_Feriados` | visível | `A1:G1420` | 1 | 1.419 | 7 | 13 | 0 | calendário |
| 21 | `ECON_AMTZ` | visível | `A1:R109` | 1 | 108 | 14 | 1.499 | 1 | cálculo auxiliar |
| 22 | `ECON_BOLETOS` | visível | `A1:AC35` | 2 | 33 | 25 | 216 | 0 | emissão/arquivo de boleto |
| 23 | `SIMULACAO_PMT` | visível | `A1:AT93` | 20 | 73 | 26 | 1.628 | 0 | simulador |
| 24 | `COMPR_RENDA` | visível | `A1:N348547` | 1 | 348.546 | 14 | 1.396.530 | 231 | cálculo auxiliar; alcance inflado |
| 25 | `ECON_FLUXO_AMORTIZACOES` | visível | `A1:Q90` | 20 | 70 | 15 | 1.026 | 0 | cálculo auxiliar |
| 26 | `ANEXO_1` | visível | `B1:AN59` | 11 | 36 | 34 | 117 | 0 | documento |
| 27 | `CET` | visível | `A1:X50` | 10 | 28 | 21 | 50 | 0 | cálculo/documento |
| 28 | `CONTRATO_EMP` | visível | `A1:XFC100` | 17 | 48 | 11 | 115 | 0 | documento; dimensão formatada ampla |
| 29 | `CLAUSULA` | visível | `A1:C100` | 9 | 39 | 1 | 2 | 0 | texto contratual |
| 30 | `ECON_AMORTIZACOES` | visível | `A1:W12121` | 1 | 12.120 | 21 | 12.930 | 0 | base operacional central |
| 31 | `ECON_EMPRESTIMOS` | visível | `A1:AE1437` | 1 | 1.436 | 30 | 2.563 | 0 | base operacional central |
| 32 | `ECON_LIQ_ANTECIP` | visível | `A1:AA18704` | 1 | 18.703 | 25 | 448.871 | 14 | cálculo/liquidação antecipada |
| 33 | `BCLI_BANCO` | visível | `A1:D176` | 1 | 175 | 3 | 0 | 0 | domínio bancário |
| 34 | `COD_CLIENTE` | visível | `A1:H9996` | 1 | 9.995 | 3 | 29.972 | 0 | gerador/auxiliar de código |
| 35 | `BCLI_NUMCPF` | visível | `A1:A1474` | 1 | 1.473 | 1 | 0 | 0 | auxiliar de CPF |
| 36 | `BCLI_EMPRESA` | visível | `A1:S1464` | 1 | 1.463 | 19 | 0 | 0 | dados profissionais |
| 37 | `Planilha1` | visível | `A1:R18` | 1 | 17 | 18 | 0 | 0 | acessos bancários; altamente sensível |
| 38 | `BCLI_DADOS_BANCARIOS` | visível | `A1:AA1459` | 1 | 1.458 | 27 | 0 | 0 | dados bancários e acessos; sensível |
| 39 | `BCLI_RENDA` | visível | `A1:AC1457` | 1 | 1.456 | 29 | 0 | 0 | renda e vínculo operacional |
| 40 | `DFEN_CONTRATO` | visível | `A1:AD1457` | 1 | 1.456 | 28 | 1.437 | 0 | base operacional central |
| 41 | `BCLI_CADASTRO` | visível | `A1:AQ1460` | 1 | 1.459 | 37 | 0 | 0 | base operacional central |
| 42 | `DASHBOARD` | visível | `A1:AR3613` | 1 | 3.612 | 36 | 11.127 | 0 | painel derivado |
| 43 | `BCLI_TEL_ADC` | visível | `A1:I15` | 1 | 7 | 9 | 0 | 0 | telefones adicionais |

### Abas ocultas

`TIPO_DOCUMENTO`, `NACIONALIDADE`, `GENERO`, `ESTADO_CIVIL`,
`ESCOLARIDADE`, `TIPO_TELEFONE`, `TIPO_RESIDENCIA`, `NATUREZA_OCUP`,
`TIPO_COMPROVANTE`, `TIPO_CONTA`, `CAD_ORGAO_SUBORGAO`, `TIPO_PRODUTO`,
`TIPO_CLIENTE` e `SIMULACAO_VL_LIBERADO`.

## 4. Bases operacionais centrais

### 4.1 `BCLI_CADASTRO`

- Cabeçalho: linha 1, alta confiança.
- Volume: 1.459 linhas não vazias e 37 colunas efetivamente usadas.
- Fórmulas e erros: nenhum.
- Colunas:
  - identidade: `COD_CLIENTE`, `CPF_CLIENTE`, `NOME_CLIENTE`;
  - pessoais: `DT_NASC`, `N_DOCUMENTO`, `ORGAO_EXP`,
    `TIPO_DOCUMENTO`, `DATA_EXPEDICAO`, `NATURALIDADE`, `UF`,
    `NACIONALIDADE`, `GENERO`, `ESTADO_CIVIL`, `ESCOLARIDADE`,
    `DEPENDENTES`, `NOME_PAI`, `NOME_MAE`;
  - endereço: `CEP_R`, `ENDERECO_R`, `NUMERO_R`, `COMPLEMENTO_R`,
    `BAIRRO_R`, `CIDADE_R`, `UF_R`, `TIPO_RESIDENCIA`, `VALOR_IMOVEL`,
    `TEMPO_R`;
  - contato: `DDD_R`, `TELEFONE_R`, `TIPO_TEL_R`, `DDD`, `TELEFONE`,
    `TIPO_TEL2`, `EMAIL`;
  - controle: `PARTICULAR`, um segundo `COD_CLIENTE` e
    `DTHORA_INCLUSAO`.

Tipos relevantes:

| Campo | Perfil observado | Observação |
|---|---|---|
| primeiro `COD_CLIENTE` | 1.457 textos e 2 números | tipo misto |
| `CPF_CLIENTE` | 1.459 textos | 209 valores distintos |
| `NOME_CLIENTE` | 1.459 textos | 258 valores distintos |
| `DT_NASC` | texto predominante, 2 datas e 3 números | 14 textos não reconhecidos como data |
| `DATA_EXPEDICAO` | 1.459 textos | 13 textos não reconhecidos como data |
| `VALOR_IMOVEL` | 1.459 textos | 1.438 valores com aparência monetária |
| segundo `COD_CLIENTE` | 1.459 textos | 319 valores distintos |

CPF e código se repetem muitas vezes: são 1.459 linhas para 209 CPFs e 319
códigos. Portanto, nenhuma dessas colunas pode ser assumida isoladamente como
chave primária da linha bruta. É necessário esclarecer se a repetição representa
histórico, contrato, versão ou outra granularidade.

### 4.2 `DFEN_CONTRATO`

- Cabeçalho: linha 1, alta confiança.
- Volume: 1.456 linhas e 28 colunas usadas.
- `COD_CONTRATO`: 1.456 valores distintos; candidato forte a chave da base.
- Colunas:
  `COD_CLIENTE`, `COD_CONTRATO`, `NUM_CPF`, `COD_ORGAO`,
  `COD_SUBORGAO`, `PRODUTO`, `SUBPRODUTO`, `TIPO_CLIENTE`, `TAB_JUR`,
  `PRAZO`, `VAL_REFIN`, `VL_DISPONIVEL`, `DT_INCLUSAO`, `DT_OPERACAO`,
  `VCTO_PRIM_PARC`, `RENDA_DISPONÍVEL`, `PRINCIPAL`, `TC`, `IOF`,
  `VL_FINANCIADO`, `PMT`, `COMPR_RENDA`, `VL_LIBERADO`, `APROVADO`,
  `BANCO_CREDITO`, `FORMA_PAGTO`, `DATA_LIBERACAO`, `VL PROJETADO`.

Tipos e fórmulas relevantes:

| Grupo/campo | Perfil observado |
|---|---|
| códigos | texto predominante, com poucos números em `COD_CLIENTE`, `COD_ORGAO` e `COD_SUBORGAO` |
| datas | armazenadas predominantemente como texto |
| valores monetários | combinação de número e texto; de 8 a 52 valores com aparência monetária como texto por coluna |
| `TAB_JUR` | 656 textos e 800 números |
| `VL_FINANCIADO` | uma fórmula; demais valores manuais |
| `DATA_LIBERACAO` | 20 fórmulas que referenciam `DT_OPERACAO`; demais valores manuais |
| `VL PROJETADO` | 1.416 fórmulas do padrão `PMT * PRAZO` |

### 4.3 `ECON_EMPRESTIMOS`

- Cabeçalho: linha 1, alta confiança.
- Volume: 1.436 linhas e 30 colunas usadas.
- `COD_CONTRATO`: 1.436 valores distintos; candidato forte a chave.
- Colunas:
  `COD_CONTRATO`, `COD_CLIENTE`, `NUM_CPF`, `COD_PRODUTO`,
  `MODALIDADE`, `COD_ORGAO`, `COD_SUBORGAO`, `DTHORA_INCLUSAO`,
  `DT_OPERACAO`, `CARENCIA`, `VENCIMENTO1`, `VL_REFIN`,
  `VL_DISPONIVEL`, `VL_PRINCIPAL`, `PRAZO_PGTO`, `TC`, `IOF`,
  `VL_FINACIADO`, `PMT`, `VL_LIBERADO`, `VECTO_CONTRATO`,
  `TAB_JUROS`, `TAXA_JUROS`, `TAXA_TIR`, `TAXA_CET_AM`,
  `TAXA_CET_AA`, `CREFISA`, `STATUS`, `DT_ATUALIZ`, `CONTROLE`.

Tipos e fórmulas relevantes:

| Grupo/campo | Perfil observado |
|---|---|
| códigos | `COD_CONTRATO` é texto; outros códigos misturam número e texto |
| datas | `DT_OPERACAO`, `VENCIMENTO1`, `VECTO_CONTRATO` e `DT_ATUALIZ` misturam texto e datas nativas |
| valores monetários | `VL_REFIN`, `VL_DISPONIVEL`, `VL_PRINCIPAL`, `IOF`, `VL_FINACIADO`, `PMT` e `VL_LIBERADO` misturam número e texto |
| taxas | `TAXA_JUROS`, `TAXA_TIR`, `TAXA_CET_AM` e `TAXA_CET_AA` são numéricas e percentuais |
| `CARENCIA` | 1.381 fórmulas, diferença entre vencimento e operação concatenada com texto |
| `VL_FINACIADO` | uma fórmula; demais valores manuais |
| `CONTROLE` | 1.181 fórmulas sequenciais |

### 4.4 `ECON_AMORTIZACOES`

- Cabeçalho: linha 1, alta confiança.
- Volume: 12.120 linhas e 21 colunas usadas.
- Colunas:
  `COD_CLIENTE`, `NUM_CPF`, `COD_CONTRATO`, `COD_PARCELA`,
  `VENCIMENTO`, `VAL_AMTZ_JUR`, `VAL_AMTZ_PRINC`, `VAL_PARCELA`,
  `BAIXA _TOTAL`, `DT_BAIXATOTAL`, `VAL_PGTO`, `DESCONTO_CONC`,
  `SD_PARCELA`, `STATUS_PARC`, `SITUACAO`, `NOME COMPLETO`, `BANCO`,
  `CHAVE`, `BOL_ANTECIP`, `BOLETO NORMAL`, `PRODUTO_FINANCEIRO`.
- `CHAVE`: 12.120 valores distintos; 12.057 são fórmulas sequenciais.
- `COD_CONTRATO`: 1.398 valores distintos, como esperado para várias
  parcelas por contrato.

Tipos e fórmulas relevantes:

| Campo | Perfil observado |
|---|---|
| `COD_CLIENTE` | 12.108 números e 12 textos |
| `NUM_CPF` | texto |
| `COD_CONTRATO` | 12.119 textos e 1 número |
| `COD_PARCELA` | numérico; 57 fórmulas sequenciais e demais valores manuais |
| `VENCIMENTO` | 12.116 datas e 4 textos; 92 fórmulas em parte das linhas |
| `VAL_AMTZ_JUR`, `VAL_AMTZ_PRINC`, `VAL_PARCELA` | numéricos, com poucas fórmulas em duas colunas |
| `VAL_PGTO` | 11.237 números e 79 textos; 695 fórmulas |
| `DESCONTO_CONC` | 7.308 números e 47 textos; 29 textos com aparência monetária |
| `DT_BAIXATOTAL` | datas; uma fórmula |

A combinação natural `COD_CONTRATO + COD_PARCELA` deve ser testada na Fase
1B, mas ainda não foi aprovada como chave. `CHAVE` é única nesta versão, porém
é calculada e não deve ser adotada automaticamente como identificador estável
entre versões do arquivo.

## 5. Relacionamentos comprovados

As comparações foram feitas com valores normalizados e mascarados; nenhum
identificador real foi gravado no relatório.

| Relação | Valores relacionados | Linhas filhas relacionadas | Órfãs | Cobertura |
|---|---:|---:|---:|---:|
| `BCLI_CADASTRO.CPF_CLIENTE` → `DFEN_CONTRATO.NUM_CPF` | 209 | 1.456 | 0 | 100,00% |
| `BCLI_CADASTRO.COD_CLIENTE` → `DFEN_CONTRATO.COD_CLIENTE` | 318 | 1.455 | 1 | 99,93% |
| `DFEN_CONTRATO.COD_CONTRATO` → `ECON_EMPRESTIMOS.COD_CONTRATO` | 1.433 | 1.433 | 3 | 99,79% |
| `DFEN_CONTRATO.COD_CONTRATO` → `ECON_AMORTIZACOES.COD_CONTRATO` | 1.397 | 12.108 | 12 | 99,90% |
| `ECON_EMPRESTIMOS.COD_CONTRATO` → `ECON_AMORTIZACOES.COD_CONTRATO` | 1.395 | 12.106 | 14 | 99,88% |

Conclusões:

- CPF liga integralmente o cadastro aos contratos nesta versão.
- Código de cliente possui uma ocorrência de contrato sem correspondente no
  cadastro normalizado.
- Há três empréstimos sem contrato correspondente em `DFEN_CONTRATO`.
- Há 12 amortizações sem contrato em `DFEN_CONTRATO` e 14 sem empréstimo em
  `ECON_EMPRESTIMOS`.
- A diferença entre 12 e 14 indica que duas referências existem no contrato,
  mas não na base de empréstimos.
- A cardinalidade observada é cliente 1:N contratos e contrato 1:N parcelas.

## 6. Inconsistências e riscos encontrados

### Alta prioridade para o futuro espelho

1. **Granularidade do cadastro não definida:** 1.459 linhas representam apenas
   209 CPFs e 319 códigos. O espelho bruto deve preservar linhas; uma entidade
   canônica de cliente exige regra de negócio explícita.
2. **Órfãos entre bases:** 1 código de cliente, 3 empréstimos e 12/14
   amortizações não encontram pai conforme as relações acima. Devem entrar na
   fila de inconsistências, nunca ser descartados silenciosamente.
3. **CPF inválido:** foram detectadas 20 ocorrências que não passam na
   normalização/validação em `ECON_AMORTIZACOES.NUM_CPF`.
4. **Valores monetários como texto:** há ocorrências nas quatro bases,
   inclusive 1.438 em `BCLI_CADASTRO.VALOR_IMOVEL`. O parser deverá usar
   `Decimal`, tratar separadores brasileiros e rejeitar ambiguidades.
5. **Datas heterogêneas:** datas nativas, números seriais e textos coexistem.
   Foram encontrados 14 candidatos inválidos em `DT_NASC` e 13 em
   `DATA_EXPEDICAO`.
6. **Colunas parcialmente calculadas:** há campos que misturam fórmulas e
   entradas manuais. O futuro reader não poderá pressupor que uma coluna é
   integralmente calculada ou integralmente manual.
7. **Tipos mistos em chaves:** códigos de cliente, órgão, subórgão e contrato
   aparecem ora como texto, ora como número. Devem ser preservados como
   identificadores textuais normalizados, não convertidos para inteiro.

### Segurança e minimização de dados

O esquema contém colunas com nomes de senha, token, acesso eletrônico,
homebanking e senha de cartão em `CAD_USUARIOS`, `Planilha1` e
`BCLI_DADOS_BANCARIOS`. O diagnóstico não expôs seus valores.

Essas abas e colunas não devem ser importadas por um leitor genérico. A Fase 1B
precisa usar lista positiva de abas e colunas aprovada antes da implementação.
Essa é uma decisão pendente; este relatório não altera sozinho o escopo.

### Erros de célula do Excel

| Tipo | Quantidade |
|---|---:|
| `#NAME?` | 1.056 |
| `#VALUE!` | 421 |
| `#REF!` | 232 |
| `#N/A` | 14 |
| **Total** | **1.723** |

Distribuição:

| Aba | Erros |
|---|---:|
| `SIMULACAO_VL_LIBERADO` | 1.477 |
| `COMPR_RENDA` | 231 |
| `ECON_LIQ_ANTECIP` | 14 |
| `ECON_AMTZ` | 1 |

As quatro bases centrais não possuem células de erro nesta versão. Foram
detectadas seis fórmulas contendo referência quebrada. Os erros estão em áreas
derivadas/simuladores e devem ser registrados caso alguma delas seja futuramente
aprovada para importação.

### Limites das heurísticas

- As dimensões de `REGRAS_PV` e `COMPR_RENDA` são infladas por fórmulas
  pré-preenchidas; “linha não vazia” não significa registro válido.
- Resultados de fórmulas sem cache não foram recalculados.
- A detecção de data inválida é sintática; regras de datas sentinela precisam
  ser definidas pelo negócio.
- Repetição de CPF, código ou parcela não é automaticamente duplicidade:
  depende da granularidade da aba.

## 7. Diferenças em relação às suposições anteriores

1. A fonte operacional possui 43 abas, não as 19 do arquivo legado.
2. Os nomes das quatro bases centrais coincidem em parte com o legado, mas
   colunas, volumes, tipos, fórmulas e relacionamentos são diferentes.
3. `BCLI_CADASTRO` não se comporta como cadastro canônico de uma linha por
   cliente.
4. `DFEN_CONTRATO` e `ECON_EMPRESTIMOS` possuem chaves de contrato únicas,
   mas não têm correspondência total entre si.
5. `ECON_AMORTIZACOES` contém a agenda e a baixa operacional de parcelas, com
   fórmulas apenas em subconjuntos de linhas.
6. Não existem tabelas estruturadas do Excel; o contrato do FileSource terá de
   ser baseado em cabeçalhos e validação de esquema.
7. Há macros, conexões de CEP e milhões de fórmulas. A leitura precisa continuar
   isolada em cópia, sem macro, sem atualização externa e sem recálculo.
8. O arquivo inclui dados sensíveis fora do escopo mínimo de clientes e
   contratos. Uma importação automática de todas as abas seria incompatível
   com minimização de dados e segurança.
9. O relatório do `Funding Remo.xlsm` continua útil apenas para o módulo futuro
   de funding e reconciliação; ele não define este mapeamento.

## 8. Mapeamento preliminar, ainda não aprovado

Este quadro é uma classificação diagnóstica, não uma alteração da arquitetura.

| Grupo | Abas | Tratamento sugerido para decisão |
|---|---|---|
| núcleo operacional | `BCLI_CADASTRO`, `DFEN_CONTRATO`, `ECON_EMPRESTIMOS`, `ECON_AMORTIZACOES` | candidatas ao primeiro espelho |
| apoio operacional | domínios `TIPO_*`, `ORGAO_EMISSOR`, `PRODUTO_MODAL`, `Cadastro_Feriados`, `BCLI_BANCO`, `BCLI_EMPRESA`, `BCLI_RENDA`, `BCLI_TEL_ADC` | importar somente se houver dependência aprovada |
| derivadas/cálculo | `REGRAS_PV`, simuladores, `ECON_AMTZ`, `COMPR_RENDA`, `ECON_FLUXO_AMORTIZACOES`, `ECON_LIQ_ANTECIP`, `DASHBOARD`, `COD_CLIENTE` | não tratar como fonte bruta sem decisão específica |
| documentos/apresentação | `Imagem`, `ECON_BOLETOS`, `ANEXO_1`, `CET`, `CONTRATO_EMP`, `CLAUSULA` | fora do espelho inicial |
| acesso/alto risco | `CAD_USUARIOS`, `Planilha1` e campos de acesso de `BCLI_DADOS_BANCARIOS` | bloquear por padrão |
| auxiliares a esclarecer | `BCLI_NUMCPF`, `CAD_ORGAO_SUBORGAO` | validar função e necessidade |

## 9. Decisões necessárias antes da Fase 1B

1. Qual é a granularidade das linhas repetidas de `BCLI_CADASTRO`?
2. Qual regra escolhe o cliente canônico quando CPF ou código se repete?
3. O primeiro ou o segundo `COD_CLIENTE` de `BCLI_CADASTRO` é o identificador
   autoritativo?
4. `DFEN_CONTRATO` ou `ECON_EMPRESTIMOS` prevalece quando valores do mesmo
   contrato divergem?
5. Como tratar os contratos, empréstimos e amortizações órfãos?
6. A chave de parcela deve ser `COD_CONTRATO + COD_PARCELA`, `CHAVE` ou outro
   identificador?
7. Quais abas e colunas de apoio entram no primeiro espelho?
8. Quais colunas de dados bancários são realmente necessárias, excluindo
   acessos e credenciais?
9. Textos monetários vazios, marcadores e formatos brasileiros devem virar
   `NULL` ou inconsistência?
10. Fórmulas devem ser lidas pelo valor em cache, ignoradas ou substituídas por
    campos calculados pelo backend em fase posterior?

## 10. Conclusão

O arquivo correto foi localizado e é tecnicamente legível por cópia local. As
quatro bases centrais e seus principais relacionamentos foram confirmados, mas
o diagnóstico revela que o espelho não pode ser construído com uma regra
genérica de “uma aba = uma tabela” nem com CPF/código como chave automática.

A Fase 1B deve aguardar aprovação expressa deste relatório e resposta às
decisões de mapeamento. Até lá:

- o Excel permanece intocável;
- `LocalFileSource` não foi implementado;
- nenhuma migration foi criada;
- nenhum dado foi enviado ao Supabase;
- nenhuma funcionalidade de funding, investidor, aporte, rateio, remuneração,
  dashboard ou autenticação foi iniciada.

## Apêndice A — Cabeçalhos das demais abas

Somente nomes de colunas são apresentados; valores foram omitidos.

- `CAD_USUARIOS`: `NOME`, `CPF`, `DT_NASCIMENTO`, `CARGO`, `USUARIO`,
  `SENHA`, `VALIDADE`, `STATUS`, `STATUS PARC`, `FONTE PAGADORA`,
  `AGÊNCIA/CONTROLE`.
- `TIPO_DOCUMENTO`: `TIPO_DOCUMENTO`, `N_DOCJUMENTO`.
- `NACIONALIDADE`: `NACIONALIDADE`, `COD_NAC`.
- `GENERO`: `GENERO`, `TIPO_GENERO`.
- `ESTADO_CIVIL`: `ESTADO CIVIL`, `COD_EST_CIVIL`.
- `ESCOLARIDADE`: `ESCOLARIDADE`, `TIPO_ESCOLARIDADE`.
- `TIPO_TELEFONE`: `TIPO_TELEFONE`, `COD_TELEFONE`.
- `TIPO_RESIDENCIA`: `TIPO_RESIDENCIA`, `COD_RESIDENCIA`.
- `NATUREZA_OCUP`: `NATUREZA DE OCUPAÇÃO`, `COD_NATUREZA_OCUP`.
- `TIPO_COMPROVANTE`: `TIPO DE COMPROVANTE`, `COD_COMPROVANTE`.
- `TIPO_CONTA`: `TIPO_CONTA`, `NUM_TIPO`.
- `CAD_ORGAO_SUBORGAO`: `COD_ORGA`, `DESC_ORGAO`, `COD_SUB_ORGAO`,
  `DESC_SUBORGAO`, `COD_PRODUTO`, `DESC_PRODUTO`, `COD_SUBPRODUTO`,
  `DESC_SUBPRODUTO`, `REGRA_PAGAMENTO`, `REGRA_VENCIMENTO`, `VIRADA`.
- `TIPO_PRODUTO`: `TIPO_PRODUTO`, `COD_TIPO_PROD`.
- `TIPO_CLIENTE`: `TIPO_CLIENTE`, `DESCRIÇÃO`, `COD_TIPO_CLIENTE`.
- `ORGAO_EMISSOR`: `ORGAO_EMISSOR`, `COD_ORGAO`, `TIPO_DOCUMENTO`,
  `N_DOCJUMENTO`, `NACIONALIDADE`, `COD_NAC`, `GENERO`, `TIPO_GENERO`,
  `ESTADO CIVIL`, `COD_EST_CIVIL`, `UF`.
- `PRODUTO_MODAL`: `MODALIDADE`, `CHAVE2`, `PRODUTO`, `MODADLIDAE`,
  `TIPO_CLIENTE`, `CODIGO`, `SUB_ORGAO`, `RATING`, `PRAZO`, `CARENCIA`,
  `TABELA DE JUROS`, `JUROS a.m.`, `JUROS a.a.`, `CÓD`,
  `DESCRICAO_MODAL`, `CLASS` e blocos auxiliares de produto/modalidade.
- `REGRAS_PV`: códigos e descrições de órgão/subórgão, chaves, regras de
  pagamento/vencimento, virada e blocos de cálculo de dias úteis.
- `SIMULACAO_VL_LIBERADO`: prazo, vencimento, carência, amortização, juros,
  parcela, CET, saldos e IOF.
- `Cadastro_Feriados`: `Data`, `Dia da Semana`, `Feriado`, `PRORROGA`,
  `DIA_SEMANA`, `SEMANA`, `dias_prorrog`.
- `ECON_AMTZ`: `Prazo`, `Vencimento`, `Carência`, `Amortizacao`, `Juros`,
  `VlParcela`, `CodCliente`, `NumCPF`, `CodContrato`, `STATUS`,
  `NOME_CLIENTE`, `BANCO`, `id`, `Modal`.
- `ECON_BOLETOS`: identificação, contato, endereço, número, valor,
  vencimento, cancelamento, negativação, instruções, juros, multa e desconto.
- `SIMULACAO_PMT`: prazo, vencimento, carência, amortização, juros, parcela,
  CET, saldos e IOF.
- `COMPR_RENDA`: cabeçalho composto por fórmulas; não há tabela de origem
  estável comprovada.
- `ECON_FLUXO_AMORTIZACOES`: bloco calculado com `COD_CLIENTE`, `NUM_CPF`,
  `COD_CONTRATO`, `STATUS`, `NOME` e `BANCO`.
- `ANEXO_1`: blocos repetidos de `Parcela`, `Valor (R$)` e `Vencimento`.
- `CET`: blocos repetidos de `Parcela`, `Valor (R$)` e `Vencimento`.
- `CONTRATO_EMP`: campos de emissão do documento, nascimento, estado civil,
  sexo e naturalidade em layout documental.
- `CLAUSULA`: texto contratual, sem tabela operacional.
- `ECON_LIQ_ANTECIP`: cliente, CPF, contrato, parcela, vencimento, pagamento,
  desconto, saldo, situação, banco, juros, mora, multa e controle de boleto.
- `BCLI_BANCO`: `COD_BANCO`, `NOME_BANCO`, `SITE_BANCO`.
- `COD_CLIENTE`: `CPF`, `COD_CLIENTE`, `COD_AUTOMÁTICO`.
- `BCLI_NUMCPF`: `NUM_CPF`.
- `BCLI_EMPRESA`: contrato, cliente, CPF, empresa, cargo, ocupação,
  comprovante, telefone e endereço profissional.
- `Planilha1`: CPF, nome, banco, agência, conta e campos de senha, usuário,
  token e acesso; valores deliberadamente não analisados no relatório.
- `BCLI_DADOS_BANCARIOS`: contrato, cliente, CPF, banco, agência, conta,
  tipo de conta, dados de transferência e campos de acesso bancário.
- `BCLI_RENDA`: contrato, cliente, CPF, órgão, subórgão, ocupação, benefício,
  matrícula, rendas, empréstimos, saldo, empresa, telefone e endereço.
- `DASHBOARD`: safra, contratos, principal, projetado, recebido, descontos,
  vencido, inadimplência e blocos auxiliares de KPI.
- `BCLI_TEL_ADC`: `NUM_CPF`, dois blocos de DDD, telefone, tipo e comentário.

