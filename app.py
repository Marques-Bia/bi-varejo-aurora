"""
Painel de BI - Varejo Aurora (dados simulados)

Trabalho de Big Data Analytics e Business Intelligence - Uniso, 6º semestre.
Tema: Um guia para implementação de Business Intelligence.
Grupo: Beatriz Marques, Gustavo Diniz, Kaio Vitor e Guilherme Ruiz.
Professor: César Candido Xavier.

Rodar localmente:  streamlit run app.py
"""
from datetime import date

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from etl import NOMES_MES, executar_etl

# ------------------------------------------------------------------ visual
AZUL_UNISO = "#293796"
AMARELO_UNISO = "#FFDF00"
TINTA = "#1B2470"
TINTA_SUAVE = "#5A6188"
GRADE = "#E4E8F6"
SERIE = "#3949B5"      # série principal dos gráficos
DESTAQUE = "#D97706"   # segunda série / atenção (par validado para daltonismo)
NEUTRO = "#A8AEC8"

st.set_page_config(
    page_title="BI Varejo Aurora | Uniso",
    page_icon="uniso_simbolo.png",
    layout="wide",
)

st.markdown(
    f"""
    <style>
    .block-container {{padding-top: 3.5rem; padding-bottom: 3rem;}}
    h1, h2, h3 {{color: {TINTA}; letter-spacing: -0.5px;}}
    [data-testid="stMetric"] {{
        background: #FDFDFF; border: 1px solid #DFE3F2; border-top: 5px solid {AMARELO_UNISO};
        border-radius: 16px; padding: 16px 20px;
    }}
    [data-testid="stMetricLabel"] p {{font-size: 1.05rem; color: {TINTA_SUAVE};}}
    [data-testid="stMetricValue"] {{font-size: 2.1rem; font-weight: 700; color: {TINTA};}}
    .faixa {{background: {AZUL_UNISO}; color: #F7F8FC; border-radius: 16px; padding: 18px 24px; margin: 4px 0 12px;}}
    .faixa b {{color: {AMARELO_UNISO};}}
    .nota {{color: {TINTA_SUAVE}; font-size: 0.95rem;}}
    .stTabs [data-baseweb="tab"] p {{font-size: 1.1rem; font-weight: 600;}}
    </style>
    """,
    unsafe_allow_html=True,
)


# ------------------------------------------------------------- utilidades
def brl(valor, casas=0):
    texto = f"{valor:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {texto}"


def brl_curto(valor):
    if abs(valor) >= 1_000_000:
        return f"R$ {valor / 1_000_000:.2f} mi".replace(".", ",")
    if abs(valor) >= 1_000:
        return f"R$ {valor / 1_000:.0f} mil"
    return brl(valor)


def pct(valor, casas=1):
    return f"{valor:.{casas}f}%".replace(".", ",")


def rotulo_mes(periodo):
    p = pd.Period(periodo, freq="M")
    return f"{NOMES_MES[p.month - 1]}/{str(p.year)[2:]}"


def estilo(fig, altura=380, legenda=True):
    fig.update_layout(
        height=altura,
        template="plotly_white",
        font=dict(family="DM Sans, Arial, sans-serif", size=15, color=TINTA),
        margin=dict(l=10, r=20, t=30, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        showlegend=legenda,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
        hoverlabel=dict(bgcolor="#FDFDFF", font_size=14, font_color=TINTA),
    )
    fig.update_xaxes(showgrid=False, linecolor=GRADE, tickfont=dict(color=TINTA_SUAVE))
    fig.update_yaxes(gridcolor=GRADE, zeroline=False, tickfont=dict(color=TINTA_SUAVE))
    return fig


# ------------------------------------------------------------------- dados
@st.cache_data(show_spinner="Gerando os dados e rodando o ETL (só demora na primeira vez)...")
def carregar_dados():
    # na nuvem os CSVs não vão para o repositório: são gerados na primeira execução (cerca de 15 s)
    from pathlib import Path
    if not (Path(__file__).parent / "vendas_brutas.csv").exists():
        import gerar_dados
        gerar_dados.gerar_tudo()
    modelo, relatorio, antes, depois, amostra = executar_etl()
    base = (modelo["fato_vendas"]
            .merge(modelo["dim_loja"][["loja_id", "loja", "canal"]], on="loja_id")
            .merge(modelo["dim_produto"][["produto_id", "produto", "categoria"]], on="produto_id"))
    base["mes"] = base["data"].dt.to_period("M").astype(str)
    return modelo, base, relatorio, antes, depois, amostra


modelo, base, relatorio_etl, qualidade_antes, qualidade_depois, amostra_bruta = carregar_dados()
DATA_MIN = base["data"].min().date()
DATA_MAX = base["data"].max().date()


# ----------------------------------------------------------------- sidebar
st.logo("uniso_logo.png", size="large", icon_image="uniso_simbolo.png")
with st.sidebar:
    st.markdown("### Filtros")
    periodo = st.date_input(
        "Período",
        value=(date(2026, 1, 1), DATA_MAX),
        min_value=DATA_MIN,
        max_value=DATA_MAX,
        format="DD/MM/YYYY",
    )
    if isinstance(periodo, (tuple, list)) and len(periodo) == 2:
        inicio, fim = periodo
    else:  # usuário ainda está escolhendo a data final
        inicio = periodo[0] if isinstance(periodo, (tuple, list)) else periodo
        fim = DATA_MAX
    todas_lojas = sorted(base["loja"].unique())
    lojas_sel = st.multiselect("Lojas", todas_lojas, default=todas_lojas)
    todas_cats = sorted(base["categoria"].unique())
    cats_sel = st.multiselect("Categorias", todas_cats, default=todas_cats)
    st.divider()
    st.caption(
        "Big Data Analytics e Business Intelligence · Uniso · 6º semestre  \n"
        "Beatriz Marques, Gustavo Diniz, Kaio Vitor e Guilherme Ruiz  \n"
        "Prof. César Candido Xavier"
    )

if not lojas_sel or not cats_sel:
    st.warning("Selecione pelo menos uma loja e uma categoria nos filtros.")
    st.stop()

ini_ts, fim_ts = pd.Timestamp(inicio), pd.Timestamp(fim)
dur = fim_ts - ini_ts + pd.Timedelta(days=1)
INICIO_DADOS = pd.Timestamp(DATA_MIN)

recorte = base[base["loja"].isin(lojas_sel) & base["categoria"].isin(cats_sel)]
atual = recorte[recorte["data"].between(ini_ts, fim_ts)]


def janela_anterior(ini, fim_):
    """Período de mesmo tamanho imediatamente antes (usado no churn). None se não houver dados."""
    d = fim_ - ini + pd.Timedelta(days=1)
    a_ini = ini - d
    if a_ini < INICIO_DADOS:
        return None
    return recorte[recorte["data"].between(a_ini, ini - pd.Timedelta(days=1))]


# comparação com o mesmo período do ano anterior (respeita a sazonalidade do varejo)
ano_ini, ano_fim = ini_ts - pd.DateOffset(years=1), fim_ts - pd.DateOffset(years=1)
tem_ano_anterior = ano_ini >= INICIO_DADOS
ano_anterior = recorte[recorte["data"].between(ano_ini, ano_fim)] if tem_ano_anterior else None

with st.sidebar:
    st.download_button(
        "Baixar dados filtrados (CSV)",
        atual.drop(columns=["mes"]).to_csv(index=False).encode("utf-8-sig"),
        file_name="vendas_filtradas.csv",
        mime="text/csv",
        width="stretch",
    )


# ------------------------------------------------------------- indicadores
def indicadores(df, df_janela_anterior):
    receita = df["receita"].sum()
    pedidos = df["id_pedido"].nunique()
    ticket = receita / pedidos if pedidos else 0.0
    online = df.dropna(subset=["no_prazo"]).groupby("id_pedido")["no_prazo"].first()
    no_prazo = online.mean() * 100 if len(online) else np.nan
    churn = np.nan
    if df_janela_anterior is not None:
        clientes_antes = set(df_janela_anterior["cliente_id"])
        clientes_agora = set(df["cliente_id"])
        if clientes_antes:
            churn = len(clientes_antes - clientes_agora) / len(clientes_antes) * 100
    return {"receita": receita, "pedidos": pedidos, "ticket": ticket, "no_prazo": no_prazo, "churn": churn}


k = indicadores(atual, janela_anterior(ini_ts, fim_ts))
k0 = indicadores(ano_anterior, janela_anterior(ano_ini, ano_fim)) if tem_ano_anterior else None


def delta_pct(atual_v, anterior_v):
    if k0 is None or not anterior_v or pd.isna(anterior_v):
        return None
    return pct((atual_v / anterior_v - 1) * 100)


def delta_pp(atual_v, anterior_v):
    if k0 is None or pd.isna(anterior_v) or pd.isna(atual_v):
        return None
    return f"{atual_v - anterior_v:+.1f}".replace(".", ",") + " p.p."


# ---------------------------------------------------------------- cabeçalho
st.markdown(
    f"<p style='color:{AZUL_UNISO};font-weight:700;letter-spacing:2px;text-transform:uppercase;margin-bottom:0'>"
    "Um guia para implementação de Business Intelligence</p>",
    unsafe_allow_html=True,
)
st.title("Painel de BI · Varejo Aurora")
st.markdown(
    f"<p class='nota'>Empresa e dados <b>fictícios</b>, gerados para demonstração. "
    f"Período selecionado: <b>{inicio:%d/%m/%Y} a {fim:%d/%m/%Y}</b>. "
    + ("Variações comparam com o <b>mesmo período do ano anterior</b>. " if tem_ano_anterior
       else "Sem dados do ano anterior para comparar este período. ")
    + f"Dados disponíveis até {DATA_MAX:%d/%m/%Y}.</p>",
    unsafe_allow_html=True,
)

abas = st.tabs(["Visão geral", "Diagnóstico", "Previsão", "Qualidade e ETL", "Modelo de dados", "Sobre o projeto"])

# ============================================================ VISÃO GERAL
with abas[0]:
    st.caption("Análise **descritiva**: o que aconteceu no período?")
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Receita", brl_curto(k["receita"]), delta_pct(k["receita"], k0 and k0["receita"]))
    c2.metric("Pedidos", f"{k['pedidos']:,}".replace(",", "."), delta_pct(k["pedidos"], k0 and k0["pedidos"]))
    c3.metric("Ticket médio", brl(k["ticket"], 2), delta_pct(k["ticket"], k0 and k0["ticket"]))
    c4.metric("Taxa de churn", pct(k["churn"]) if not pd.isna(k["churn"]) else "—",
              delta_pp(k["churn"], k0 and k0["churn"]), delta_color="inverse",
              help="Clientes que compraram no período anterior e não voltaram a comprar neste período.")
    c5.metric("Entregas no prazo", pct(k["no_prazo"]) if not pd.isna(k["no_prazo"]) else "—",
              delta_pp(k["no_prazo"], k0 and k0["no_prazo"]),
              help="Pedidos do e-commerce entregues até a data prevista.")

    st.markdown("#### Receita mensal x meta")
    mensal = atual.groupby("mes")["receita"].sum()
    lojas_ids = modelo["dim_loja"].set_index("loja").loc[lojas_sel, "loja_id"]
    metas = (modelo["metas"][modelo["metas"]["loja_id"].isin(lojas_ids) & modelo["metas"]["mes"].isin(mensal.index)]
             .groupby("mes")["meta_receita"].sum())
    fig = go.Figure()
    x = [rotulo_mes(m) for m in mensal.index]
    fig.add_trace(go.Scatter(x=x, y=mensal.values, name="Receita realizada", mode="lines+markers",
                             line=dict(color=SERIE, width=3), marker=dict(size=9),
                             hovertemplate="%{x}<br>Receita: R$ %{y:,.0f}<extra></extra>"))
    mostrar_meta = set(cats_sel) == set(todas_cats)
    if mostrar_meta and len(metas):
        fig.add_trace(go.Scatter(x=[rotulo_mes(m) for m in metas.index], y=metas.values, name="Meta",
                                 mode="lines", line=dict(color=DESTAQUE, width=2, dash="dash"),
                                 hovertemplate="%{x}<br>Meta: R$ %{y:,.0f}<extra></extra>"))
    fig.update_layout(hovermode="x unified", separators=",.")
    fig.update_yaxes(tickprefix="R$ ", tickformat=",.0f")
    st.plotly_chart(estilo(fig, 400), width="stretch")
    if not mostrar_meta:
        st.caption("A meta é definida por loja (não por categoria); ela aparece quando todas as categorias estão selecionadas.")
    elif len(metas):
        abaixo = [rotulo_mes(m) for m in metas.index if mensal.get(m, 0) < metas[m]]
        if abaixo:
            st.caption(f"Meses abaixo da meta: **{', '.join(abaixo)}**.")
        else:
            st.caption("Todos os meses do período bateram a meta.")

    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("#### Receita por categoria")
        por_cat = atual.groupby("categoria")["receita"].sum().sort_values()
        fig = go.Figure(go.Bar(x=por_cat.values, y=por_cat.index, orientation="h", marker_color=SERIE,
                               text=[brl_curto(v) for v in por_cat.values], textposition="outside",
                               hovertemplate="%{y}: R$ %{x:,.0f}<extra></extra>"))
        fig.update_xaxes(showticklabels=False, range=[0, por_cat.max() * 1.25] if len(por_cat) else None)
        st.plotly_chart(estilo(fig, 340, legenda=False), width="stretch")
    with col_b:
        st.markdown("#### Receita por loja")
        por_loja = atual.groupby("loja")["receita"].sum().sort_values()
        fig = go.Figure(go.Bar(x=por_loja.values, y=por_loja.index, orientation="h", marker_color=SERIE,
                               text=[brl_curto(v) for v in por_loja.values], textposition="outside",
                               hovertemplate="%{y}: R$ %{x:,.0f}<extra></extra>"))
        fig.update_xaxes(showticklabels=False, range=[0, por_loja.max() * 1.25] if len(por_loja) else None)
        st.plotly_chart(estilo(fig, 340, legenda=False), width="stretch")

    st.markdown("#### Produtos que mais faturaram")
    top = (atual.groupby(["produto", "categoria"])
           .agg(receita=("receita", "sum"), unidades=("quantidade", "sum"))
           .sort_values("receita", ascending=False).head(10).reset_index())
    st.dataframe(
        top, hide_index=True, width="stretch",
        column_config={
            "produto": "Produto", "categoria": "Categoria",
            "receita": st.column_config.ProgressColumn("Receita (R$)", format="R$ %.0f", min_value=0,
                                                       max_value=float(top["receita"].max()) if len(top) else 1),
            "unidades": st.column_config.NumberColumn("Unidades", format="%d"),
        },
    )

# ============================================================ DIAGNÓSTICO
with abas[1]:
    st.caption("Análise **diagnóstica**: por que aconteceu? E, ao final, uma sugestão de ação (**prescritiva**).")
    meses_periodo = sorted(atual["mes"].unique())
    meses_validos = [m for m in meses_periodo if (pd.Period(m, "M") - 3) >= pd.Period(DATA_MIN, "M")]
    if not meses_validos:
        st.info("Escolha um período que termine pelo menos 4 meses após o início dos dados.")
    else:
        mes_sel = st.selectbox("Mês analisado", meses_validos, index=len(meses_validos) - 1, format_func=rotulo_mes)
        p_sel = pd.Period(mes_sel, "M")
        refs = [str(p_sel - i) for i in (1, 2, 3)]
        st.markdown(f"Comparação do mês analisado com a **média dos 3 meses anteriores** "
                    f"({', '.join(rotulo_mes(r) for r in reversed(refs))}).")

        rec_mes = recorte[recorte["mes"] == mes_sel].groupby("loja")["receita"].sum()
        rec_ref = recorte[recorte["mes"].isin(refs)].groupby("loja")["receita"].sum() / 3
        var = ((rec_mes / rec_ref - 1) * 100).dropna().sort_values(ascending=False)

        st.markdown("#### Variação da receita por loja")
        cores = [DESTAQUE if v < -15 else SERIE for v in var.values]
        fig = go.Figure(go.Bar(
            x=var.values, y=var.index, orientation="h", marker_color=cores,
            text=[f"{v:+.0f}%".replace("-", "−") + ("  queda forte" if v < -15 else "") for v in var.values],
            textposition="outside",
            hovertemplate="%{y}: %{x:.1f}%<extra></extra>"))
        lim = max(abs(var.min()), abs(var.max()), 10) * 1.6
        fig.update_xaxes(range=[-lim, lim], ticksuffix="%", zeroline=True, zerolinecolor=TINTA_SUAVE)
        fig.update_yaxes(autorange="reversed")
        st.plotly_chart(estilo(fig, 320, legenda=False), width="stretch")

        pior = var.idxmin()
        loja_diag = st.selectbox("Investigar a loja", list(var.index), index=list(var.index).index(pior))

        dados_loja = recorte[recorte["loja"] == loja_diag]
        dias_mes = p_sel.days_in_month
        dias_ref = sum(pd.Period(r, "M").days_in_month for r in refs)
        ped_ref = (dados_loja[dados_loja["mes"].isin(refs)].groupby("hora")["id_pedido"].nunique() / dias_ref)
        ped_mes = (dados_loja[dados_loja["mes"] == mes_sel].groupby("hora")["id_pedido"].nunique() / dias_mes)
        horas = range(int(min(ped_ref.index.min(), ped_mes.index.min() if len(ped_mes) else 23)),
                      int(max(ped_ref.index.max(), ped_mes.index.max() if len(ped_mes) else 0)) + 1)
        ped_ref = ped_ref.reindex(horas, fill_value=0)
        ped_mes = ped_mes.reindex(horas, fill_value=0)

        st.markdown(f"#### Pedidos por hora do dia · Loja {loja_diag}")
        fig = go.Figure()
        fig.add_trace(go.Bar(x=[f"{h}h" for h in horas], y=ped_ref.values, name="Média dos 3 meses anteriores",
                             marker_color=SERIE, hovertemplate="%{x}: %{y:.1f} pedidos/dia<extra></extra>"))
        fig.add_trace(go.Bar(x=[f"{h}h" for h in horas], y=ped_mes.values, name=f"{rotulo_mes(mes_sel)}",
                             marker_color=DESTAQUE, hovertemplate="%{x}: %{y:.1f} pedidos/dia<extra></extra>"))
        fig.update_layout(barmode="group", bargap=0.25, bargroupgap=0.08)
        fig.update_yaxes(title_text="pedidos por dia")
        st.plotly_chart(estilo(fig, 360), width="stretch")

        # faixas horárias que "sumiram"
        perdidas = [h for h in horas if ped_ref[h] >= 0.3 and ped_mes[h] < 0.05]
        rec_hora_ref = (dados_loja[dados_loja["mes"].isin(refs)].groupby("hora")["receita"].sum() / dias_ref)
        perda_mensal = float(rec_hora_ref.reindex(perdidas, fill_value=0).sum() * 30)
        variacao_loja = var[loja_diag]

        col1, col2 = st.columns([1.1, 1])
        with col1:
            st.markdown("#### O que os dados mostram")
            if perdidas:
                faixas = ", ".join(f"{h}h" for h in perdidas)
                st.markdown(
                    f"- A receita da Loja **{loja_diag}** variou **{pct(variacao_loja, 0)}** em {rotulo_mes(mes_sel)}.\n"
                    f"- As vendas **sumiram** nas faixas de **{faixas}**, que antes eram movimentadas.\n"
                    f"- Nas demais horas o movimento ficou parecido. O problema é de **horário de funcionamento**, "
                    f"não de demanda.")
            else:
                st.markdown(
                    f"- A receita da Loja **{loja_diag}** variou **{pct(variacao_loja, 0)}** em {rotulo_mes(mes_sel)}.\n"
                    "- Não há faixa horária que tenha zerado. Vale investigar outras dimensões, "
                    "como categoria e produto (use os filtros ao lado).")
        with col2:
            st.markdown("#### Ação sugerida")
            if perdidas:
                st.markdown(
                    f"<div class='faixa'>Avaliar a volta do horário estendido na Loja {loja_diag}.<br>"
                    f"Receita potencial a recuperar: <b>{brl(perda_mensal)} por mês</b>, "
                    f"estimada pela média das faixas {', '.join(f'{h}h' for h in perdidas)} nos 3 meses anteriores.</div>",
                    unsafe_allow_html=True)
            else:
                st.markdown("<div class='faixa'>Sem causa evidente por horário. Aprofundar a análise por "
                            "categoria e produto antes de decidir.</div>", unsafe_allow_html=True)

# =============================================================== PREVISÃO
with abas[2]:
    st.caption("Análise **preditiva**: o que deve acontecer nos próximos meses?")
    hist = recorte.groupby("mes")["receita"].sum()
    hist.index = pd.PeriodIndex(hist.index, freq="M")
    ultimo = hist.index.max()
    ult6 = [ultimo - i for i in range(6)]
    mesmos_ano_ant = [p - 12 for p in ult6]
    if all(p in hist.index for p in mesmos_ano_ant):
        crescimento = hist[ult6].sum() / hist[mesmos_ano_ant].sum()
        futuros = [ultimo + i for i in (1, 2, 3)]
        previsao = pd.Series([hist[p - 12] * crescimento for p in futuros], index=futuros)

        m1, m2 = st.columns(2)
        m1.metric("Crescimento recente (últimos 6 meses x mesmo período do ano anterior)", pct((crescimento - 1) * 100))
        m2.metric(f"Receita prevista ({rotulo_mes(futuros[0])} a {rotulo_mes(futuros[-1])})", brl_curto(previsao.sum()))

        fig = go.Figure()
        fig.add_trace(go.Scatter(x=[rotulo_mes(p) for p in hist.index], y=hist.values, name="Realizado",
                                 mode="lines+markers", line=dict(color=SERIE, width=3), marker=dict(size=8),
                                 hovertemplate="%{x}: R$ %{y:,.0f}<extra></extra>"))
        fig.add_trace(go.Scatter(x=[rotulo_mes(ultimo)] + [rotulo_mes(p) for p in futuros],
                                 y=[hist[ultimo]] + list(previsao.values), name="Previsão",
                                 mode="lines+markers", line=dict(color=DESTAQUE, width=3, dash="dash"),
                                 marker=dict(size=10, symbol="diamond"),
                                 hovertemplate="%{x}: R$ %{y:,.0f}<extra></extra>"))
        fig.update_layout(hovermode="x unified", separators=",.")
        fig.update_yaxes(tickprefix="R$ ", tickformat=",.0f")
        st.plotly_chart(estilo(fig, 420), width="stretch")

        st.dataframe(
            pd.DataFrame({"Mês": [rotulo_mes(p) for p in futuros],
                          "Mesmo mês do ano anterior": [brl(hist[p - 12]) for p in futuros],
                          "Previsão": [brl(v) for v in previsao.values]}),
            hide_index=True, width="stretch")
        st.markdown(
            "<p class='nota'><b>Como a previsão é feita:</b> receita do mesmo mês do ano anterior × crescimento "
            "dos últimos 6 meses. É um método simples (sazonal ingênuo com ajuste de tendência), bom como ponto de "
            "partida. Ele não sabe de eventos novos: se o horário da Loja Centro não voltar ao normal, a previsão "
            "tende a ser otimista para essa loja. Os filtros de loja e categoria valem aqui; o de período, não "
            "(a previsão usa todo o histórico).</p>",
            unsafe_allow_html=True)
    else:
        st.info("São necessários pelo menos 18 meses de histórico para esta previsão.")

# ======================================================== QUALIDADE E ETL
with abas[3]:
    st.caption("Etapa 3 do guia (dados) e etapa 4 (arquitetura): como o dado bruto vira dado confiável.")
    linhas_brutas = int(qualidade_antes["Linhas"])
    linhas_finais = int(qualidade_depois["Linhas"])
    q1, q2, q3 = st.columns(3)
    q1.metric("Linhas brutas", f"{linhas_brutas:,}".replace(",", "."))
    q2.metric("Linhas após o ETL", f"{linhas_finais:,}".replace(",", "."))
    q3.metric("Linhas descartadas", f"{linhas_brutas - linhas_finais:,}".replace(",", "."),
              help="Duplicados, produtos inexistentes e linhas sem quantidade.")

    st.markdown("#### Qualidade antes e depois do ETL")
    dims = ["Completude", "Unicidade", "Validade", "Consistência", "Precisão"]
    regras = {
        "Completude": "Campos obrigatórios preenchidos",
        "Unicidade": "Sem linhas repetidas",
        "Validade": "Data no padrão, preço > 0 e produto existente",
        "Consistência": "Nome da loja igual ao cadastro oficial",
        "Precisão": "Preço igual ao do catálogo",
    }
    st.dataframe(
        pd.DataFrame({
            "Dimensão": dims,
            "Regra": [regras[d] for d in dims],
            "Antes (%)": [round(qualidade_antes[d], 2) for d in dims],
            "Depois (%)": [round(qualidade_depois[d], 2) for d in dims],
        }),
        hide_index=True, width="stretch",
        column_config={
            "Antes (%)": st.column_config.ProgressColumn("Antes", format="%.2f%%", min_value=80, max_value=100),
            "Depois (%)": st.column_config.ProgressColumn("Depois", format="%.2f%%", min_value=80, max_value=100),
        },
    )
    st.caption(f"Atualidade: os dados vão até {DATA_MAX:%d/%m/%Y}. Escala das barras começa em 80% para mostrar a diferença.")

    st.markdown("#### O que o ETL fez, passo a passo")
    st.dataframe(relatorio_etl, hide_index=True, width="stretch",
                 column_config={"Linhas afetadas": st.column_config.NumberColumn(format="%d")})

    with st.expander("Ver amostra dos dados brutos (antes do ETL)"):
        st.caption("Nomes e e-mails são fictícios. Eles existem só aqui, no dado bruto: o ETL os troca por um código.")
        st.dataframe(amostra_bruta, hide_index=True, width="stretch")
    with st.expander("Ver amostra da tabela fato (depois do ETL)"):
        st.dataframe(modelo["fato_vendas"].head(8), hide_index=True, width="stretch")

# ======================================================= MODELO DE DADOS
with abas[4]:
    st.caption("Modelagem dimensional (Kimball): uma tabela fato no centro e as dimensões ao redor.")
    col1, col2 = st.columns([1.2, 1])
    with col1:
        st.graphviz_chart(f"""
        graph estrela {{
            graph [bgcolor="transparent", pad="0.3", nodesep="0.6", ranksep="0.9"];
            node [shape=box, style="rounded,filled", fontname="Helvetica", fontsize=13,
                  fillcolor="#FDFDFF", color="{AZUL_UNISO}", fontcolor="{TINTA}", penwidth=2, margin="0.25,0.12"];
            edge [color="{AZUL_UNISO}", penwidth=2];
            fato [label="fato_vendas\\nreceita · quantidade · desconto\\nentrega no prazo", fillcolor="{AZUL_UNISO}",
                  fontcolor="white", fontsize=15];
            tempo [label="dim_tempo\\ndata · mês · trimestre"];
            loja [label="dim_loja\\nloja · cidade · canal"];
            produto [label="dim_produto\\nproduto · categoria · preço"];
            cliente [label="dim_cliente\\ncódigo · cidade"];
            tempo -- fato; loja -- fato; fato -- produto; fato -- cliente;
        }}
        """, width="stretch")
    with col2:
        st.markdown("**Tabela fato:** um registro por item vendido, com as medidas numéricas.")
        st.markdown("**Dimensões:** dão contexto à venda: quando, onde, o quê e para quem.")
        tamanhos = pd.DataFrame({
            "Tabela": list(modelo.keys()),
            "Linhas": [len(t) for t in modelo.values()],
            "Colunas": [t.shape[1] for t in modelo.values()],
        })
        st.dataframe(tamanhos, hide_index=True, width="stretch")
    tabela = st.selectbox("Ver tabela", list(modelo.keys()))
    st.dataframe(modelo[tabela].head(20), hide_index=True, width="stretch")

# ======================================================== SOBRE O PROJETO
with abas[5]:
    st.markdown("### Como este painel aplica o guia")
    st.dataframe(
        pd.DataFrame([
            ("1. Diagnóstico", "Pergunta de negócio: por que a receita caiu em setembro?", "Diagnóstico"),
            ("2. KPIs", "Receita, pedidos, ticket médio, churn, entregas no prazo e meta", "Visão geral"),
            ("3. Dados", "Seis fontes de problema tratadas e qualidade medida antes e depois", "Qualidade e ETL"),
            ("4. Arquitetura", "Pipeline ETL em Python (etl.py) carregando um modelo estrela", "Modelo de dados"),
            ("5. Ferramentas", "Python + pandas + Streamlit + Plotly, todos de código aberto", "—"),
            ("6. Dashboards", "KPIs no topo, um gráfico por pergunta, cor só para destaque", "Todas"),
            ("7. Governança", "Clientes pseudonimizados (LGPD); dados pessoais não chegam ao painel", "Qualidade e ETL"),
        ], columns=["Etapa do guia", "Como aparece no painel", "Aba"]),
        hide_index=True, width="stretch")
    st.markdown("### Os quatro níveis de análise")
    st.markdown(
        "- **Descritiva** (o que aconteceu): aba *Visão geral*\n"
        "- **Diagnóstica** (por que aconteceu): aba *Diagnóstico*\n"
        "- **Preditiva** (o que vai acontecer): aba *Previsão*\n"
        "- **Prescritiva** (o que fazer): quadro *Ação sugerida*, na aba *Diagnóstico*")
    st.markdown("### Sobre os dados")
    st.markdown(
        "A Varejo Aurora **não existe**. Os dados foram gerados pelo script `gerar_dados.py` para simular uma rede "
        "com quatro lojas físicas na região de Sorocaba e uma loja online, de janeiro de 2025 a setembro de 2026. "
        "Os dados brutos foram criados com erros propositais (duplicados, nulos, preços inválidos, nomes de loja "
        "diferentes, datas em dois formatos) para demonstrar o ETL. Também foi simulada uma mudança no horário da "
        "Loja Centro a partir de setembro de 2026, que o painel ajuda a descobrir.")
    st.markdown("### Equipe")
    st.markdown(
        "Beatriz Marques · Gustavo Diniz · Kaio Vitor · Guilherme Ruiz  \n"
        "Professor: César Candido Xavier  \n"
        "Big Data Analytics e Business Intelligence · 6º semestre · Universidade de Sorocaba (Uniso)")
