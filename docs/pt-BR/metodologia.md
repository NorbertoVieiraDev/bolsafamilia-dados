# Metodologia e limites

## Unidade e tempo

O agregado é município × mês da referência devolvida pela CGU. O favorecido é o titular do pagamento; a quantidade retornada não é o total de integrantes das famílias. Até conciliar com a documentação operacional, a interface usa “beneficiados informados pela fonte”. Competência é o mês ao qual a parcela se refere; referência é a folha em que aparece. O detalhamento preserva ambos. Não se presume data efetiva de saque: a API chama o campo `valorSaque`, mas não fornece `dataSaque` no esquema consultado.

## Agregação

Valores monetários são validados com Decimal e convertidos para centavos inteiros. Total anual é soma dos valores mensais disponíveis. Quantidade anual é média mensal dos quantitativos, nunca soma. Média do benefício no período = soma dos valores / soma dos quantitativos mensais (média ponderada por beneficiado-mês). O último mês disponível é mostrado nos indicadores; não é confundido com pessoas únicas no ano.

Brasil e UF são agregações dos municípios. Uma resposta vazia não é zero. A cobertura compara os municípios recebidos ao catálogo IBGE preservado; contagem de municípios, mudanças territoriais e diferenças entre bases exigem revisão. Só municípios explicitamente presentes contribuem. Totais incompletos devem ser rotulados como parciais e não apresentados como total oficial nacional. Dezembro ausente não pode ser substituído silenciosamente por outro mês num indicador chamado “dezembro”.

2023 começa em março. Anos incompletos são marcados. Comparação percentual só ocorre com conjuntos idênticos de meses e cobertura completa em ambos os períodos. Comparações entre Bolsa Família antigo, Auxílio Brasil e Novo Bolsa Família exigem séries separadas e notas de mudança; não foram implementadas.

## Detalhamento

A lista mensal apresenta as parcelas retornadas, podendo haver mais de uma por titular. O acumulado anual agrupa pelo NIS disponível na fonte antes de remover os identificadores da saída. Homônimos não são fundidos por nome. CPF mascarado não é usado como identificador de agrupamento; ausência de NIS interrompe o detalhamento. Um nome pode mudar no tempo; esse caso exige conciliação. A lista informa os meses cobertos; ausência de coleta é diferente de lista coletada vazia. O total de parcelas individuais deve ser conciliado com o agregado municipal antes de publicar como equivalente: as bases podem representar conceitos ou calendários distintos.

## IPCA

A versão inicial exibe valores nominais. Correção exige uma série oficial de índices, mês-base explícito e aplicação parcela/mês a parcela/mês antes da soma anual. Não se aplica um único fator anual a todos os pagamentos. A interface não oferece correção antes de importar e validar esses índices.

## Atualização

Executar piloto autenticado, validar esquema e conciliar total/quantidade com o Portal. Coletar o período nacional, conferir cobertura, preservar originais e manifestos, gerar nova release imutável e revisar antes de hospedar. Reconsultar meses recentes para capturar revisões; não sobrescrever releases já publicadas. Não há agendamento ativo nesta versão.
