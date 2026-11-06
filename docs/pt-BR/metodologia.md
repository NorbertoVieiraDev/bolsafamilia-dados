# Metodologia e limites

## Fonte, cobertura e geografia

O histórico publicado foi obtido de 43 ZIPs mensais oficiais do Novo Bolsa Família, de março/2023 a setembro/2026. São 859.194.021 linhas de origem. O inventário encontrou 5.570 municípios nos arquivos iniciais e 5.571 nos recentes; o catálogo da página é a união dos códigos observados. Outubro/2026 retornou HTTP 403 e não foi tratado como mês de pagamentos zero.

Os CSVs usam códigos **SIAFI**, distintos de IBGE. Identificadores da página são explicitamente `siafi-XXXX`; não se inventa uma conversão. UF e nome municipal vêm do próprio arquivo. Cobertura geográfica usa as contagens do arquivo mensal, respeitando mudanças municipais no tempo. Ausência de um município/período não vira zero.

A API da CGU é usada para conciliar amostras: São Paulo/202601, Rio Branco/202303 e Rio de Janeiro/202406 coincidiram em valor e quantidade. Os relatórios dos pilotos e o manifesto completo dos arquivos estão em `reports/`. A amostragem não é certificação pela API de todas as células da base.

## Períodos, parcelas e contagens

Todas as linhas têm a competência validada contra o arquivo solicitado. Referências de folhas anteriores são preservadas: parcelas retroativas não são descartadas. O mês do arquivo/competência organiza a série financeira; a referência original é outro campo. Não se presume data efetiva de saque.

Valores são convertidos com decimal exato em centavos inteiros. O total anual soma os meses disponíveis. A quantidade mensal é NIS distintos por município mais cada registro sem NIS, mantido separado. São favorecidos/registros identificáveis na base, não todos os membros das famílias. A quantidade anual do gráfico é a média dos quantitativos mensais; nunca a soma como se fossem pessoas únicas. O valor médio mensal é soma dos valores / soma dos quantitativos mensais, ponderado por beneficiado-mês.

2023 cobre março–dezembro e 2026 cobre janeiro–setembro. Anos parciais são marcados. Variação percentual usa exatamente os mesmos meses do ano anterior e exige cobertura completa dos arquivos correspondentes. Programas antecessores (Bolsa Família antigo e Auxílio Brasil) não estão integrados.

## Valor da época e valor corrigido pelo IPCA

**Valor da época (nominal)** é o montante registrado na base. **Valor corrigido pelo IPCA** é uma equivalência monetária para comparar poder de compra em um mês-base comum. Os dois aparecem simultaneamente no indicador principal, na tabela da série e no CSV; gráfico/ranking permitem alternar a base.

A série oficial utilizada é a SGS 433 (IPCA mensal), publicada pelo Banco Central. A consulta de 06/11/2026 retornou setembro/2026 como último índice disponível. O original consultado está em `sources/ipca-20261106.json`, com hash no manifesto.

Para um total municipal no mês m, o fator é o produto de `(1 + IPCA mensal / 100)` de m+1 até o mês-base. Cada total municipal mensal é corrigido e arredondado a centavos antes de somar anos, UFs ou Brasil. Não se usa um único fator anual para todos os pagamentos. Índice ausente interrompe a correção; não há extrapolação de inflação não publicada. O mês-base é explícito junto do valor corrigido. As listas individuais exibem valores nominais, identificados como tais.

## Listas individuais e privacidade

Os acumulados anuais agrupam localmente por município e NIS para distinguir homônimos; quando não há NIS, cada linha tem chave local própria e não é fundida pelo nome. Essas chaves, NIS e CPF não entram na saída pública de consulta. Somente nome, valor e nome normalizado para busca são publicados, com autorização explícita do responsável nos projetos Cloudflare Pages destinados ao site. Homônimos podem continuar aparecendo como linhas distintas com o mesmo nome/valor.

As saídas são ordenadas e divididas em partes de 10 mil registros. Índices de limites alfabéticos permitem contar e paginar buscas de prefixo lendo apenas partes necessárias. O navegador recebe páginas de 25 registros. Estão disponíveis acumulados anuais e a competência mais recente; isso não significa disponibilidade de lista mensal de todas as competências históricas.

## Integridade, reprodução e atualização

ZIPs, CSVs intermediários e Parquets pessoais ficam fora do Git. O processamento conserva SHA-256 do ZIP, CRC do membro, contagem de linhas, somas monetárias e contagem municipal. Cada etapa confere somas antes de liberar a próxima; as tabelas anuais e os arquivos sanitizados preservam os montantes. São hashes calculados pelo projeto, não assinaturas oficiais da CGU.

Os nomes/valores de consulta são hospedados separadamente do Git; o repositório público conserva extração, metodologia, índices de inflação e evidências agregadas. A página tem código em repositório privado separado. Não há chave CGU no navegador/site: ela permanece no GitHub Actions para o piloto autenticado.

Não há cronograma automático ativo. Para nova coleta/revisão, usar diretório e release novos, reconsultar as fontes oficiais, preservar os originais e comparar eventuais revisões. Não sobrescrever releases que atendem produção. A página e os cinco conjuntos de consulta usam URLs imutáveis coordenadas; mesmo quando a plataforma os chama de “preview”, os IDs ativos devem ser protegidos como produção.
