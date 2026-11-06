# Bolsa Família — dados e metodologia

[English](docs/en/README.md) · [Metodologia](docs/pt-BR/metodologia.md)

Extração reproduzível dos dados oficiais do Novo Bolsa Família, publicados pela CGU. Projeto independente, sem vínculo com CGU, MDS ou Caixa. A interface fica em outro repositório privado; este contém somente código de obtenção/preparação, documentação e evidências agregadas. Bases, nomes de beneficiários e credenciais não são versionados.

## Estado

Implementação inicial, com especificação oficial consultada em 06/11/2026. **Nenhuma coleta autenticada de produção foi realizada.** Testes usam dados sintéticos. Não há total nacional certificado nem atualização automática ativa. A série preparada começa em março de 2023; programas antecessores não foram integrados.

## Reprodução

Requer Python 3.10+, sem dependências externas.

```sh
python scripts/extract.py catalog
# Configure PORTAL_TRANSPARENCIA_API_KEY no ambiente seguro de execução.
# Piloto limitado: município de São Paulo, um mês.
python scripts/extract.py collect --start 202601 --end 202601 --city 3550308 --output work/releases/piloto
python scripts/extract.py collect --kind beneficiaries --start 202601 --end 202601 --city 3550308 --output work/releases/piloto
python -m unittest discover -s tests -v
```

Omitir `--city` coleta todos os municípios do catálogo IBGE. **Não inicie a carga nacional antes de validar o piloto e estimar chamadas, duração, armazenamento e cobertura.** Cada página, inclusive a vazia que encerra a consulta, é registrada por URL sem chave e SHA-256. O limite conservador é 120 chamadas/minuto, com repetição para 429/5xx. Respostas locais são reutilizadas; `--refresh` reconsulta a fonte. Use um novo diretório de release para cada publicação; o script não faz deploy nem grava em serviços de hospedagem.

A extração de beneficiários deve cobrir todo o período desejado numa execução para gerar o acumulado anual. CPF/NIS e identificadores são descartados da saída de exibição; identificadores originais são usados apenas em memória para distinguir homônimos. Os originais locais ficam em `work/raw`, fora do Git.

## API oficial

Base: `https://api.portaldatransparencia.gov.br/api-de-dados/`. Autenticação: cabeçalho `chave-api-dados`, recebido exclusivamente de variável de ambiente.

| Endpoint | Uso |
| --- | --- |
| `novo-bolsa-familia-por-municipio` | Total e quantidade de beneficiados por município/mês |
| `novo-bolsa-familia-sacado-beneficiario-por-municipio` | Parcelas dos favorecidos de um município/mês |
| `novo-bolsa-familia-sacado-por-nis` | Consulta individual disponível na fonte; não usada pelo coletor |
| `novo-bolsa-familia-sacado-por-cpf-ou-nis` | Consulta individual disponível na especificação atual; não usada pelo coletor |

Consultas municipais usam `mesAno=AAAAMM`, `codigoIbge` de sete dígitos e `pagina`, começando em 1. A paginação termina somente em resposta vazia. Falhas não são interpretadas como zero. Alterações inesperadas de esquema, escopo, duplicação ou paginação interrompem a coleta.

- [Swagger/OpenAPI](https://api.portaldatransparencia.gov.br/)
- [Cadastro da chave](https://portaldatransparencia.gov.br/api-de-dados/cadastrar-email)
- [Dicionário oficial](https://portaldatransparencia.gov.br/dicionario-de-dados/novo-bolsa-familia)
- [Arquivos mensais oficiais](https://portaldatransparencia.gov.br/download-de-dados/novo-bolsa-familia)
- [Origem e atualização](https://portaldatransparencia.gov.br/origem-dos-dados)

`sources/openapi-subset.json` conserva o recorte consultado e o hash da especificação completa. Os CSVs mensais são uma alternativa de obtenção para cargas grandes; **o importador CSV ainda não está implementado**. Não misture totais de fontes diferentes sem conciliação.

## Integridade e transparência

O coletor preserva respostas originais e publica manifestos com hashes dos bytes recebidos. São hashes calculados por este projeto, não assinaturas nem hashes fornecidos pela CGU. Provam identidade dos arquivos conservados; não comprovam completude ou exatidão da fonte. Os relatórios não incluem chave, respostas individuais, CPF/NIS ou caminhos privados.

Veja a metodologia para valores, contagens, lacunas, anos parciais e limites. Código e documentação original: MIT; dados oficiais conservam os termos e a atribuição de suas fontes.

## Conferir uma release

```sh
python scripts/verify.py work/releases/piloto --report work/releases/piloto/verification.json
```

O verificador confere duplicações, centavos inteiros, catálogo e cobertura, calcula hashes dos arquivos gerados e compara parcelas disponíveis com o agregado municipal. Divergências são explicitadas e exigem investigação; não são corrigidas artificialmente. O relatório contém somente códigos territoriais, métricas e hashes. Pode ser revisado e copiado para um diretório público de relatórios após uma coleta real. A lista de exibição é dividida em páginas de 25 registros e índices por três primeiras letras, permitindo busca de prefixo sem carregar todo o município no navegador.

Se o serviço do IBGE estiver indisponível, o comando de catálogo faz tentativas limitadas e falha explicitamente. Um original JSON obtido da mesma URL oficial pode ser processado offline com `catalog --input caminho/municipios.json`; seu hash será preservado. Não use catálogo de terceiros ou lista municipal fictícia para preencher cobertura.
