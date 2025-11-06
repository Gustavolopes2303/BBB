import streamlit as st
from datetime import date
from dateutil.relativedelta import relativedelta
import pandas as pd
import altair as alt

# --- 1. CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(
    page_title="Calculadora Rescisória Completa v2.1 (CLT)",
    page_icon="⚖️",
    layout="wide"
)

# --- 2. TABELAS DE IMPOSTOS (Mantidas) ---

def get_inss_aliquota_e_deducao(salario_base):
    """
    Calcula o INSS com base na tabela progressiva.
    Faixa: (teto da faixa, alíquota, dedução)
    """
    # Tabela INSS Progressiva (exemplo com valores de 2025)
    faixas = [
        (1518.00, 0.075, 0.00),
        (2793.88, 0.09, 22.77),
        (4190.83, 0.12, 106.59),
        (8157.41, 0.14, 190.40)
    ]
    if salario_base <= 0: return 0.0
    
    base_calculo = min(salario_base, faixas[-1][0])
    
    # Percorre as faixas (do menor para o maior teto) para encontrar a alíquota e dedução corretas
    for teto, aliquota, deducao in faixas:
        if base_calculo <= teto:
            # Aplica a fórmula: (Base x Alíquota) - Parcela a Deduzir
            return (base_calculo * aliquota) - deducao
            
    # Caso a base seja superior ao Teto (8157.41), aplica o valor máximo (Teto x Alíquota Máxima - Dedução)
    aliquota_teto = faixas[-1][1]
    deducao_teto = faixas[-1][2]
    return (faixas[-1][0] * aliquota_teto) - deducao_teto


def get_irrf_aliquota_e_deducao(base_ir):
    # Tabela IRRF (Exemplo pós-maio/2025)
    faixas = [
        (2428.80, 0.00, 0.00),
        (2826.65, 0.075, 182.16),
        (3751.05, 0.15, 394.16),
        (4664.68, 0.225, 675.49),
        (999999.00, 0.275, 908.73)
    ]
    if base_ir <= 0: return 0.0
        
    for teto, aliquota, deducao in faixas:
        if base_ir <= teto:
            return (base_ir * aliquota) - deducao
    
    return (base_ir * faixas[-1][1]) - faixas[-1][2]

# --- 3. FUNÇÕES DE CÁLCULO (Lógica Trabalhista COM REFERÊNCIAS) ---

def calcular_dias_ferias(faltas):
    """Calcula os dias de férias aos quais o empregado tem direito (Art. 130 CLT)."""
    if faltas <= 5:
        return 30
    elif faltas <= 14:
        return 24
    elif faltas <= 23:
        return 18
    elif faltas <= 32:
        return 12
    else: # Acima de 32 faltas injustificadas
        return 0

def calcular_meses_proporcionais(admissao, demissao, faltas_prop):
    """
    Calcula os meses proporcionais para 13º e Férias (regra dos 15 dias - Lei 4.090/62).
    """
    if demissao <= admissao:
        return 0, 0
        
    # Calcula os meses brutos (regra dos 15 dias)
    diferenca = relativedelta(demissao.replace(day=1), admissao.replace(day=1))
    total_meses = diferenca.years * 12 + diferenca.months + 1

    # Ajusta se o dia da demissão for < 15
    if demissao.day < 15 and diferenca.months > 0:
          total_meses -= 1
          
    # O 13º proporcional (Lei 4.090/62) não é reduzido pelas faltas.
    # A redução de Férias Proporcionais é aplicada no cálculo da verba (dias_ferias_prop_devidos).
    
    return total_meses, total_meses 


def calcular_ferias_vencidas(salario_base, ferias_vencidas_completas, ferias_vencidas_dobro, faltas_vencidas):
    """Calcula o valor das Férias Vencidas (simples e em dobro - Art. 137 CLT) com redução por faltas."""
    
    valor_vencidas_total = 0.0
    dias_devidos = calcular_dias_ferias(faltas_vencidas) 
    
    if dias_devidos > 0:
        # Férias Simples
        valor_base_simples = (salario_base / 30) * dias_devidos
        valor_terco_simples = valor_base_simples / 3
        valor_total_simples = (valor_base_simples + valor_terco_simples) * ferias_vencidas_completas
        valor_vencidas_total += valor_total_simples

        # Férias em Dobro
        valor_base_dobro = valor_base_simples * 2
        valor_terco_dobro = valor_terco_simples * 2 
        valor_total_dobro = (valor_base_dobro + valor_terco_dobro) * ferias_vencidas_dobro
        valor_vencidas_total += valor_total_dobro
        
    return valor_vencidas_total


def calcular_aviso_previo_indenizado(admissao, demissao, salario_base):
    """Calcula o Aviso Prévio Indenizado com a proporcionalidade (Lei 12.506/11)."""
    
    # A contagem para o AP é sempre até o fim do contrato (que se estende pelo AP indenizado)
    tempo_servico = relativedelta(demissao, admissao)
    anos_trabalhados = tempo_servico.years
    
    dias_ap = 30 # 30 dias (CLT, Art. 487)
    dias_adicionais = min(anos_trabalhados * 3, 60) # Adicionais (Lei 12.506/11)
    dias_ap += dias_adicionais
    
    valor_dia = salario_base / 30.0
    valor_ap = valor_dia * dias_ap
    
    return valor_ap, dias_ap

def calcular_saldo_salario(salario_base, dias_trabalhados_no_mes):
    """Calcula o Saldo de Salário (CLT, Art. 462)."""
    valor_dia = salario_base / 30.0
    saldo = valor_dia * dias_trabalhados_no_mes
    return saldo

# --- 4. INTERFACE STREAMLIT ---

st.title("⚖️ Calculadora de Rescisão Trabalhista (v2.1 Corrigida)")
st.markdown("### Inclui Férias Vencidas, Faltas e Cálculo de Impostos")
st.caption("Simulação para Demissão **Sem Justa Causa** (Iniciativa do Empregador) - **Referências CLT**.")

st.markdown("---")

# 4.1. Entrada de Dados
st.subheader("1. Dados Contratuais e Financeiros")

col_sal, col_fgts, col_vencidas = st.columns(3)

with col_sal:
    salario_base = st.number_input("Salário Mensal Bruto (R$):", min_value=0.01, value=3000.00, step=100.00, format="%.2f")
    
with col_fgts:
    saldo_fgts_base = st.number_input("Saldo do FGTS (R$):", min_value=0.00, value=8000.00, step=100.00, format="%.2f", help="Saldo acumulado para cálculo da multa de 40% (Lei 8.036/90).")

with col_vencidas:
    ferias_vencidas_simples = st.number_input("Períodos de Férias Vencidas (Simples):", min_value=0, value=0, step=1, help="Períodos aquisitivos vencidos, mas ainda dentro do prazo legal.")
    ferias_vencidas_dobro = st.number_input("Períodos de Férias Vencidas (Em Dobro):", min_value=0, value=0, step=1, help="Períodos aquisitivos vencidos fora do prazo legal (CLT Art. 137).")

col_adm, col_dem, col_dias = st.columns(3)

with col_adm:
    data_admissao = st.date_input("Data de Admissão:", value=date(2023, 1, 1))

with col_dem:
    data_demissao = st.date_input("Data de Demissão (Efetiva):", value=date.today(), min_value=data_admissao)

with col_dias:
    dias_trabalhados = st.number_input("Dias Trabalhados no Último Mês (0 a 30):", min_value=0, max_value=31, value=20, step=1)


st.subheader("2. Impacto de Faltas Não Justificadas (CLT Art. 130)")

col_faltas_v, col_faltas_p = st.columns(2)

with col_faltas_v:
    faltas_vencidas = st.number_input("Faltas Injustificadas no Período VENCIDO (por período aquisitivo):", min_value=0, value=0, step=1, help="Faltas que reduzem os dias das Férias Vencidas (CLT Art. 130).")

with col_faltas_p:
    faltas_proporcionais = st.number_input("Faltas Injustificadas no Período PROPORCIONAL:", min_value=0, value=0, step=1, help="Faltas que reduzem os dias das Férias Proporcionais (CLT Art. 130).")
    
st.markdown("---")

# --- 5. CÁLCULO E EXIBIÇÃO ---

if st.button("Calcular Verbas Rescisórias Detalhadas", type="primary"):
    
    # 5.1. CÁLCULOS PRINCIPAIS
    
    # Saldo de Salário (CLT, Art. 462)
    valor_saldo_salario = calcular_saldo_salario(salario_base, dias_trabalhados)
    
    # Meses Proporcionais (Lei 4.090/62)
    meses_13_prop, meses_ferias_prop = calcular_meses_proporcionais(data_admissao, data_demissao, faltas_proporcionais)
    
    # 13º Salário Proporcional (Lei 4.090/62)
    valor_13_proporcional = (salario_base / 12) * meses_13_prop
    
    # Férias Proporcionais (CLT, Art. 130 e Art. 146)
    dias_ferias_prop_devidos = calcular_dias_ferias(faltas_proporcionais)
    
    # Base de cálculo proporcional em 1/12 avos
    # Formula: (Valor de um mês reduzido por faltas) / 12 * Meses proporcionais (+ 1/3)
    valor_ferias_prop_base = (salario_base / 30 * dias_ferias_prop_devidos / 12) * meses_ferias_prop
    valor_terco_prop = valor_ferias_prop_base / 3
    valor_ferias_prop_total = valor_ferias_prop_base + valor_terco_prop
    
    # Férias Vencidas (CLT, Art. 130 e Art. 137)
    valor_ferias_vencidas_total = calcular_ferias_vencidas(salario_base, ferias_vencidas_simples, ferias_vencidas_dobro, faltas_vencidas)
    
    # Aviso Prévio Indenizado (CLT, Art. 487 e Lei 12.506/11)
    valor_ap, dias_ap = calcular_aviso_previo_indenizado(data_admissao, data_demissao, salario_base)
    
    # Multa FGTS (Lei 8.036/90)
    valor_multa_fgts = saldo_fgts_base * 0.40
    
    # 5.2. TOTAL BRUTO E DESCONTOS (LÓGICA CORRIGIDA)
    
    # Aviso Prévio: Isolar o valor correspondente aos 30 dias (base) e o adicional proporcional (Lei 12.506/11).
    # O AP (30 dias) é tributável para INSS e isento de IRRF (jurisprudência). O AP Adicional é isento de INSS e IRRF.
    valor_ap_30_dias = salario_base
    # Proteção para garantir que o valor adicional não seja negativo (embora não deva ser)
    valor_ap_adicional = max(0, valor_ap - valor_ap_30_dias)

    # Base de cálculo INSS (Principal: SS + AP 30 dias). AP Adicional é isento de INSS.
    base_inss_principal = valor_saldo_salario + valor_ap_30_dias

    # 1. CÁLCULO INSS (Principal e 13º)
    inss_principal = get_inss_aliquota_e_deducao(base_inss_principal)
    inss_13 = get_inss_aliquota_e_deducao(valor_13_proporcional)

    # Base de cálculo IRRF (Principal: SS apenas, após dedução do INSS. AP Indenizado é isento de IRRF por Súmula 386 STJ).
    base_irrf_principal = valor_saldo_salario - inss_principal
    irrf_principal = get_irrf_aliquota_e_deducao(base_irrf_principal)

    total_descontos = inss_principal + irrf_principal + inss_13
    
    # Total Bruto (Pagamento Direto)
    verbas_brutas_diretas = valor_saldo_salario + valor_ap + valor_13_proporcional + valor_ferias_prop_total + valor_ferias_vencidas_total
    
    # Total Líquido (Verbas Diretas)
    verbas_pagas_liquidas = verbas_brutas_diretas - total_descontos
    
    # Saque Total (Líquido + FGTS + Multa)
    total_liquido_simulado = verbas_pagas_liquidas + saldo_fgts_base + valor_multa_fgts
    
    # 5.3. EXIBIÇÃO DOS RESULTADOS
    
    st.subheader("✅ Resumo dos Cálculos")
    
    col_liq, col_bruto, col_desc = st.columns(3)
    
    col_bruto.metric("💰 Total Verbas Brutas (Pagamento Direto)", f"R$ {verbas_brutas_diretas:,.2f}")
    col_desc.metric("✂️ Total de Descontos (INSS/IRRF Simulado)", f"R$ {total_descontos:,.2f}", delta_color="inverse")
    col_liq.metric("💵 Total de Verbas Líquidas (Pagamento Direta)", f"R$ {verbas_pagas_liquidas:,.2f}")
    
    st.success(f"## ➕ Saque FGTS e Total a Receber: R$ {total_liquido_simulado:,.2f}")
    st.caption(f"Verbas Líquidas + Saldo FGTS ({saldo_fgts_base:,.2f}) + Multa FGTS ({valor_multa_fgts:,.2f}).")

    st.markdown("---")
    
    # 5.4. DETALHAMENTO E GRÁFICOS
    
    st.subheader("📊 Detalhamento de Valores")
    
    df_verbas = pd.DataFrame({
        'Verba': ['Saldo de Salário', '13º Salário Prop. (Avos)', f'Férias Prop. (+1/3 - {dias_ferias_prop_devidos} dias)', 'Férias Vencidas (+1/3)', 'Aviso Prévio', 'Multa FGTS (40%)'],
        'Valor Bruto (R$)': [valor_saldo_salario, valor_13_proporcional, valor_ferias_prop_total, valor_ferias_vencidas_total, valor_ap, valor_multa_fgts],
        'Natureza': ['Tributável (INSS/IRRF)', 'Tributável (INSS/IRRF Separado)', 'Isenta (IRRF/INSS)', 'Isenta (IRRF/INSS)', 'INSS (30 dias) / IRRF (Isento)', 'Isenta (IRRF/INSS)']
    })
    
    df_descontos = pd.DataFrame({
        'Desconto': [f'INSS Principal (Base R$ {base_inss_principal:,.2f})', f'INSS 13º (Base R$ {valor_13_proporcional:,.2f})', f'IRRF Principal (Base R$ {base_irrf_principal:,.2f})'],
        'Valor (R$)': [inss_principal, inss_13, irrf_principal],
        'Base': ['SS e AP (30 dias)', '13º Salário Prop.', 'SS (após INSS)']
    })

    col_tabela, col_grafico = st.columns([1.5, 1])

    with col_tabela:
        st.markdown("#### Tabela de Proventos e Descontos")
        st.dataframe(df_verbas.style.format({'Valor Bruto (R$)': 'R$ {:,.2f}'}), use_container_width=True, hide_index=True)
        st.dataframe(df_descontos.style.format({'Valor (R$)': 'R$ {:,.2f}'}), use_container_width=True, hide_index=True)

    with col_grafico:
        st.markdown("#### Composição das Verbas Brutas (Pagamento Direto)")
        
        df_pie = pd.DataFrame({
            'Verba': ['Saldo Salário', '13º Prop.', 'Férias Prop.', 'Férias Vencidas/Dobro', f'Aviso Prévio'],
            'Valor': [valor_saldo_salario, valor_13_proporcional, valor_ferias_prop_total, valor_ferias_vencidas_total, valor_ap]
        })
        
        chart_pie = alt.Chart(df_pie).mark_arc(outerRadius=120).encode(
            theta=alt.Theta(field="Valor", type="quantitative"),
            color=alt.Color(field="Verba", type="nominal"),
            tooltip=['Verba', alt.Tooltip('Valor', format='$,.2f')]
        ).properties(title='Verbas Pagas Diretamente (Exclui FGTS/Multa)')
        st.altair_chart(chart_pie, use_container_width=True)

    st.markdown("---")
    
    # 5.5. FONTES E FÓRMULAS
    
    st.subheader("💡 Fontes e Fórmulas Utilizadas (Legislação)")
    
    tab_fontes, tab_inss, tab_irrf = st.tabs(["Fórmulas e Referências CLT", "Tabela INSS", "Tabela IRRF"])
    
    with tab_fontes:
        st.markdown("**1. Redução de Dias de Férias por Faltas (CLT Art. 130):**")
        st.markdown("Faltas Injustificadas no Período Aquisitivo:")
        st.markdown("- Até 5 faltas: **30 dias** de férias")
        st.markdown("- De 6 a 14 faltas: **24 dias** de férias")
        st.markdown("- De 15 a 23 faltas: **18 dias** de férias")
        st.markdown("- De 24 a 32 faltas: **12 dias** de férias")
        st.markdown("- Acima de 32 faltas: **Perde** o direito às férias")

        st.markdown("**2. Férias Vencidas (Simples e em Dobro):**")
        st.latex(r"Férias \: Vencidas = (\frac{Salário \: Base}{30} \times Dias \: Devidos) \times 1,333 \times (\text{Férias Simples} + 2 \times \text{Férias Dobro})")
        st.caption("Referência Legal: **CLT Art. 130** (Redução por Faltas) e **CLT Art. 137** (Pagamento em Dobro se fora do prazo). O adicional de $1/3$ é Constitucional (CF Art. $7^o$, XVII).")

        st.markdown("**3. Férias Proporcionais:**")
        st.latex(r"Férias \: Prop. = (\frac{Salário \: Base}{30} \times \frac{Dias \: Devidos}{12}) \times Meses \: Prop. \times 1,333")
        st.caption("Referência Legal: **CLT Art. 130** (Redução por Faltas) e **CLT Art. 146** (Proporcionalidade). Meses Prop. (1/12 avos): Fracionamento de 15 dias ou mais conta como mês completo.")
        
        st.markdown("**4. 13º Salário Proporcional:**")
        st.latex(r"13º \: Prop. = \frac{Salário \: Base}{12} \times Meses \: Prop.")
        st.caption("Referência Legal: **Lei 4.090/62**. Não é reduzido por faltas injustificadas.")
        
        st.markdown("**5. Aviso Prévio Indenizado (AP):**")
        st.latex(r"Dias \: AP = 30 \: dias \: + \: (3 \: dias \: \times \: Anos \: Completos \: de \: Serviço) \quad (\text{máx. } 90 \: dias)")
        st.caption("Referência Legal: **CLT Art. 487** (30 dias) e **Lei 12.506/11** (Proporcionalidade por ano). **ATENÇÃO:** O valor total é Isento de IRRF por Súmula 386 STJ, e o INSS incide apenas sobre os 30 dias básicos.")
        
        st.markdown("**6. Multa FGTS:**")
        st.latex(r"Multa \: FGTS = Saldo \: FGTS \times 40\%")
        st.caption("Referência Legal: **Lei 8.036/90**, Art. 18, $\S 1^o$ (Empregador sem justa causa).")

    with tab_inss:
        st.markdown("#### Tabela Progressiva INSS (Exemplo 2025/2026)")
        st.caption("Base: Portarias Interministeriais anuais. Alíquotas progressivas aplicadas apenas sobre verbas de natureza salarial.")
        st.table(pd.DataFrame({
            'Salário (Até)': ['R$ 1.518,00', 'R$ 2.793,88', 'R$ 4.190,83', 'R$ 8.157,41 (Teto)'],
            'Alíquota': ['7,5%', '9,0%', '12,0%', '14,0%'],
            'Dedução (R$)': ['0,00', '22,77', '106,59', '190,40']
        }))

    with tab_irrf:
        st.markdown("#### Tabela IRRF Mensal (Exemplo 2025/2026)")
        st.caption("Base: Lei 7.713/88 (verbas tributáveis, após dedução do INSS).")
        st.table(pd.DataFrame({
            'Base C. (Até)': ['R$ 2.428,80', 'R$ 2.826,65', 'R$ 3.751,05', 'R$ 4.664,68', 'Acima'],
            'Alíquota': ['0%', '7,5%', '15,0%', '22,5%', '27,5%'],
            'Dedução (R$)': ['0,00', '182,16', '394,16', '675,49', '908,73']
        }))
        
    st.markdown("---")
    st.info("⚠️ **Atenção:** Os cálculos são uma simulação baseada na CLT e leis correlatas. O valor final pode variar devido a Convenções Coletivas e decisões judiciais. Consulte sempre um profissional.")
