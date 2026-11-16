"""
ETL do painel: Extrai os CSVs brutos, Transforma (limpeza, padronização,
pseudonimização) e Carrega num modelo estrela (fato + dimensões) em memória.

Cada passo registra quantas linhas foram afetadas, para o painel mostrar
o "antes e depois" da qualidade dos dados.
"""
import hashlib
import unicodedata
from pathlib import Path

import numpy as np
import pandas as pd

PASTA = Path(__file__).parent
COLUNAS_OBRIGATORIAS = ["data_hora", "loja", "id_produto", "quantidade", "preco_unitario", "cliente_email"]
SAL_PSEUDONIMO = "uniso-bi-2026"  # em produção, guardar fora do código
NOMES_MES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]
DIAS_SEMANA = ["seg", "ter", "qua", "qui", "sex", "sáb", "dom"]


# ------------------------------------------------------------------ Extract
def extrair(pasta=PASTA):
    return {
        "vendas": pd.read_csv(pasta / "vendas_brutas.csv", dtype=str, keep_default_na=True),
        "produtos": pd.read_csv(pasta / "produtos.csv"),
        "lojas": pd.read_csv(pasta / "lojas.csv"),
        "metas": pd.read_csv(pasta / "metas.csv"),
    }


# --------------------------------------------------------- medir qualidade
def _sem_acento(txt):
    return "".join(c for c in unicodedata.normalize("NFKD", txt) if not unicodedata.combining(c))


def medir_qualidade(df, produtos, lojas):
    """Seis dimensões de qualidade, em % de linhas que passam na regra."""
    n = len(df)
    datas_iso = pd.to_datetime(df["data_hora"], format="%Y-%m-%d %H:%M", errors="coerce")
    preco = pd.to_numeric(df["preco_unitario"], errors="coerce")
    preco_lista = df["id_produto"].map(produtos.set_index("produto_id")["preco_lista"])
    completude = df[COLUNAS_OBRIGATORIAS].notna().all(axis=1).mean()
    unicidade = 1 - df.duplicated().mean()
    validade = (datas_iso.notna() & (preco > 0) & df["id_produto"].isin(produtos["produto_id"])).mean()
    consistencia = df["loja"].isin(lojas["loja"]).mean()
    precisao = np.isclose(preco, preco_lista).mean()
    return {
        "Completude": completude * 100,
        "Unicidade": unicidade * 100,
        "Validade": validade * 100,
        "Consistência": consistencia * 100,
        "Precisão": precisao * 100,
        "Linhas": n,
    }


# ---------------------------------------------------------------- Transform
def _padronizar_loja(nome, oficiais):
    chave = _sem_acento(str(nome)).strip().lower()
    chave = chave.replace("loja ", "").replace("shopping ", "")
    if chave == "e-commerce":
        chave = "online"
    mapa = {_sem_acento(o).lower(): o for o in oficiais}
    return mapa.get(chave, np.nan)


def _pseudonimizar(email):
    return "C" + hashlib.sha256((SAL_PSEUDONIMO + str(email)).encode()).hexdigest()[:8].upper()


def transformar(brutos):
    df = brutos["vendas"].copy()
    produtos, lojas = brutos["produtos"], brutos["lojas"]
    relatorio = []

    def passo(etapa, dimensao, descricao, afetadas):
        relatorio.append({"Etapa": etapa, "Dimensão": dimensao, "O que foi feito": descricao,
                          "Linhas afetadas": int(afetadas)})

    antes = medir_qualidade(df, produtos, lojas)

    # 1. duplicados
    n0 = len(df)
    df = df.drop_duplicates()
    passo("Remover duplicados", "Unicidade", "Linhas idênticas repetidas foram removidas", n0 - len(df))

    # 2. datas em dois formatos
    iso = pd.to_datetime(df["data_hora"], format="%Y-%m-%d %H:%M", errors="coerce")
    br = pd.to_datetime(df["data_hora"], format="%d/%m/%Y %H:%M", errors="coerce")
    passo("Padronizar datas", "Validade", "Datas no formato dd/mm/aaaa convertidas para aaaa-mm-dd",
          (iso.isna() & br.notna()).sum())
    df["data_hora"] = iso.fillna(br)

    # 3. nomes de loja
    oficiais = lojas["loja"].tolist()
    padrao = df["loja"].map(lambda x: _padronizar_loja(x, oficiais))
    passo("Padronizar lojas", "Consistência", "Variações como 'centro', 'CENTRO ' e 'Loja Centro' unificadas",
          (padrao != df["loja"]).sum())
    df["loja"] = padrao

    # 4. produto inexistente
    invalido = ~df["id_produto"].isin(produtos["produto_id"])
    passo("Remover produto inválido", "Validade", "Código de produto fora do catálogo (linha descartada)",
          invalido.sum())
    df = df[~invalido]

    # 5. quantidade nula
    df["quantidade"] = pd.to_numeric(df["quantidade"], errors="coerce")
    nula = df["quantidade"].isna()
    passo("Tratar quantidade nula", "Completude", "Sem quantidade não há como calcular a receita (linha descartada)",
          nula.sum())
    df = df[~nula]

    # 6. preço inválido -> preço de catálogo
    df["preco_unitario"] = pd.to_numeric(df["preco_unitario"], errors="coerce")
    preco_lista = df["id_produto"].map(produtos.set_index("produto_id")["preco_lista"])
    ruim = ~(df["preco_unitario"] > 0)
    passo("Corrigir preço inválido", "Precisão", "Preço zerado ou negativo substituído pelo preço do catálogo",
          ruim.sum())
    df.loc[ruim, "preco_unitario"] = preco_lista[ruim]

    # 7. LGPD: pseudonimização
    df["cliente_id"] = df["cliente_email"].map(_pseudonimizar)
    passo("Pseudonimizar clientes (LGPD)", "Segurança",
          "Nome e e-mail trocados por um código; os dados pessoais não chegam ao painel", len(df))
    df = df.drop(columns=["cliente_nome", "cliente_email"])

    depois = medir_qualidade(
        df.assign(data_hora=df["data_hora"].dt.strftime("%Y-%m-%d %H:%M"), cliente_email="ok"),
        produtos, lojas)
    return df, pd.DataFrame(relatorio), antes, depois


# --------------------------------------------------------------------- Load
def carregar(df, brutos):
    produtos, lojas, metas = brutos["produtos"], brutos["lojas"], brutos["metas"]

    datas = pd.date_range(df["data_hora"].dt.normalize().min(), df["data_hora"].dt.normalize().max(), freq="D")
    dim_tempo = pd.DataFrame({"data": datas})
    dim_tempo["ano"] = dim_tempo["data"].dt.year
    dim_tempo["mes_num"] = dim_tempo["data"].dt.month
    dim_tempo["mes"] = dim_tempo["data"].dt.to_period("M").astype(str)
    dim_tempo["nome_mes"] = dim_tempo["mes_num"].map(lambda m: NOMES_MES[m - 1])
    dim_tempo["trimestre"] = "T" + dim_tempo["data"].dt.quarter.astype(str)
    dim_tempo["dia_semana"] = dim_tempo["data"].dt.dayofweek.map(lambda d: DIAS_SEMANA[d])

    dim_loja = lojas.copy()
    dim_produto = produtos.copy()

    primeira = df.groupby("cliente_id")["data_hora"].min().dt.normalize()
    dim_cliente = (df.groupby("cliente_id")["cliente_cidade"].first().to_frame("cidade")
                   .join(primeira.rename("primeira_compra")).reset_index())

    fato = pd.DataFrame({
        "id_pedido": df["id_pedido"],
        "data": df["data_hora"].dt.normalize(),
        "hora": df["data_hora"].dt.hour,
        "loja_id": df["loja"].map(lojas.set_index("loja")["loja_id"]),
        "produto_id": df["id_produto"],
        "cliente_id": df["cliente_id"],
        "quantidade": df["quantidade"].astype(int),
        "preco_unitario": df["preco_unitario"].astype(float),
        "desconto_pct": pd.to_numeric(df["desconto_pct"]).astype(float),
        "entrega_prevista": pd.to_datetime(df["entrega_prevista"]),
        "entrega_realizada": pd.to_datetime(df["entrega_realizada"]),
    })
    fato["receita"] = (fato["quantidade"] * fato["preco_unitario"] * (1 - fato["desconto_pct"] / 100)).round(2)
    fato["no_prazo"] = np.where(fato["entrega_prevista"].isna(), np.nan,
                                (fato["entrega_realizada"] <= fato["entrega_prevista"]).astype(float))
    fato = fato.sort_values(["data", "hora", "id_pedido"]).reset_index(drop=True)

    metas = metas.merge(lojas[["loja", "loja_id"]], on="loja")[["loja_id", "mes", "meta_receita"]]

    return {
        "fato_vendas": fato,
        "dim_tempo": dim_tempo,
        "dim_loja": dim_loja,
        "dim_produto": dim_produto,
        "dim_cliente": dim_cliente,
        "metas": metas,
    }


def executar_etl(pasta=PASTA):
    brutos = extrair(pasta)
    limpo, relatorio, antes, depois = transformar(brutos)
    modelo = carregar(limpo, brutos)
    amostra_bruta = brutos["vendas"].head(8)
    return modelo, relatorio, antes, depois, amostra_bruta


if __name__ == "__main__":
    modelo, relatorio, antes, depois, _ = executar_etl()
    print(relatorio.to_string(index=False))
    print("antes:", {k: round(v, 2) for k, v in antes.items()})
    print("depois:", {k: round(v, 2) for k, v in depois.items()})
    for nome, tabela in modelo.items():
        print(nome, tabela.shape)
