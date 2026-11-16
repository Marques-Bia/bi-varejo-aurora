"""
Gera os dados SIMULADOS usados no painel.

Empresa fictícia: Varejo Aurora, rede com 4 lojas físicas na região de
Sorocaba e uma loja online. Período: 01/01/2025 a 30/09/2026.

Os dados brutos saem propositalmente com problemas de qualidade
(duplicados, nulos, preços inválidos, nomes de loja inconsistentes,
datas em formatos diferentes) para que a etapa de ETL tenha o que corrigir.

História embutida nos dados (usada na demonstração):
a partir de 01/09/2026 a Loja Centro reduziu o horário de funcionamento
(de 8h-20h para 10h-18h) e perdeu as vendas das faixas da manhã e do fim da tarde.

Uso:  python gerar_dados.py
"""
from pathlib import Path

import numpy as np
import pandas as pd

SEED = 42
INICIO = pd.Timestamp("2025-01-01")
FIM = pd.Timestamp("2026-09-30")
DATA_MUDANCA_CENTRO = pd.Timestamp("2026-09-01")
PASTA = Path(__file__).parent

rng = np.random.default_rng(SEED)

# ---------------------------------------------------------------- lojas
LOJAS = pd.DataFrame(
    [
        # id, nome, cidade, canal, abre, fecha, pedidos/dia
        ("L01", "Centro", "Sorocaba", "Loja física", 8, 20, 15),
        ("L02", "Campolim", "Sorocaba", "Loja física", 10, 22, 16),
        ("L03", "Éden", "Sorocaba", "Loja física", 8, 20, 9),
        ("L04", "Votorantim", "Votorantim", "Loja física", 8, 20, 8),
        ("L05", "Online", "Sorocaba", "E-commerce", 0, 24, 18),
    ],
    columns=["loja_id", "loja", "cidade", "canal", "abre", "fecha", "pedidos_dia"],
)

# Peso de cada hora do dia nas lojas físicas (picos antes do trabalho,
# no almoço e no fim da tarde)
PESO_HORA_FISICA = {
    8: 1.2, 9: 1.3, 10: 0.9, 11: 1.0, 12: 1.4, 13: 1.2, 14: 0.8,
    15: 0.8, 16: 0.9, 17: 1.2, 18: 1.6, 19: 1.5, 20: 1.3, 21: 1.0,
}
PESO_HORA_ONLINE = {h: (0.3 if h < 7 else 1.0 if h < 19 else 1.4 if h < 23 else 0.6) for h in range(24)}

# ------------------------------------------------------------- produtos
CATALOGO = {
    "Eletrônicos": [
        ("Fone Bluetooth", 149.9), ("Smart TV 50 polegadas", 2799.0), ("Notebook 15 polegadas", 3499.0),
        ("Caixa de som portátil", 299.9), ("Smartwatch", 899.0), ("Carregador rápido", 89.9),
        ("Mouse sem fio", 79.9), ("Tablet 10 polegadas", 1299.0),
    ],
    "Casa": [
        ("Jogo de panelas", 459.9), ("Cafeteira elétrica", 189.9), ("Jogo de cama casal", 229.9),
        ("Luminária de mesa", 99.9), ("Air fryer", 499.0), ("Toalha de banho", 49.9),
        ("Organizador de gavetas", 39.9), ("Liquidificador", 179.9),
    ],
    "Moda": [
        ("Camiseta básica", 59.9), ("Calça jeans", 169.9), ("Tênis casual", 279.9),
        ("Jaqueta corta-vento", 249.9), ("Vestido midi", 199.9), ("Boné", 69.9),
        ("Mochila", 189.9), ("Meia (kit 3 pares)", 39.9),
    ],
    "Esportes": [
        ("Tênis de corrida", 499.9), ("Bola de futebol", 129.9), ("Garrafa térmica", 89.9),
        ("Tapete de yoga", 119.9), ("Halter 5 kg", 99.9), ("Bicicleta aro 29", 1899.0),
        ("Corda de pular", 39.9), ("Mochila de hidratação", 159.9),
    ],
    "Beleza": [
        ("Perfume 100 ml", 249.9), ("Hidratante corporal", 49.9), ("Kit maquiagem", 159.9),
        ("Secador de cabelo", 219.9), ("Protetor solar", 69.9), ("Shampoo profissional", 89.9),
        ("Escova alisadora", 279.9), ("Sabonete (kit 4)", 29.9),
    ],
}
linhas = []
pid = 1
for cat, itens in CATALOGO.items():
    for nome, preco in itens:
        linhas.append((f"P{pid:03d}", nome, cat, preco))
        pid += 1
PRODUTOS = pd.DataFrame(linhas, columns=["produto_id", "produto", "categoria", "preco_lista"])
# produtos baratos vendem mais
peso_prod = 1 / PRODUTOS["preco_lista"].to_numpy() ** 0.8
peso_prod = peso_prod / peso_prod.sum()

# ------------------------------------------------------------- clientes
NOMES = ["Ana", "Bruno", "Carla", "Daniel", "Eduarda", "Felipe", "Gabriela", "Henrique", "Isabela",
         "João", "Larissa", "Lucas", "Mariana", "Mateus", "Natália", "Otávio", "Paula", "Rafael",
         "Sofia", "Thiago", "Vanessa", "Vinícius", "Yasmin", "Pedro", "Júlia", "Gustavo", "Camila",
         "Rodrigo", "Letícia", "André"]
SOBRENOMES = ["Silva", "Santos", "Oliveira", "Souza", "Rodrigues", "Ferreira", "Alves", "Pereira",
              "Lima", "Gomes", "Costa", "Ribeiro", "Martins", "Carvalho", "Almeida", "Lopes",
              "Soares", "Fernandes", "Vieira", "Barbosa"]
CIDADES = ["Sorocaba"] * 6 + ["Votorantim"] * 2 + ["Itu", "Salto", "Piedade", "Araçoiaba da Serra"]

N_CLIENTES = 4500
dias_total = (FIM - INICIO).days + 1
cli_nome = [f"{rng.choice(NOMES)} {rng.choice(SOBRENOMES)}" for _ in range(N_CLIENTES)]
cli_email = [
    f"{n.split()[0].lower()}.{n.split()[1].lower()}{i}@exemplo.com".translate(
        str.maketrans("áâãéêíóôõúç", "aaaeeiooouc"))
    for i, n in enumerate(cli_nome)
]
cli_cidade = rng.choice(CIDADES, N_CLIENTES)
# janela em que o cliente está "ativo" (permite medir churn)
cli_inicio = rng.integers(-200, dias_total - 30, N_CLIENTES)
cli_duracao = rng.exponential(420, N_CLIENTES).astype(int) + 60
cli_fim = cli_inicio + cli_duracao
cli_peso = rng.pareto(1.5, N_CLIENTES) + 1  # poucos clientes compram muito

# ---------------------------------------------------------- sazonalidade
SAZ_MES = {1: 0.90, 2: 0.85, 3: 0.95, 4: 0.95, 5: 1.08, 6: 1.00, 7: 0.95, 8: 1.00,
           9: 0.98, 10: 1.00, 11: 1.35, 12: 1.45}
SAZ_DIA = {0: 0.95, 1: 0.95, 2: 1.00, 3: 1.00, 4: 1.10, 5: 1.25, 6: 0.80}


def horas_validas(loja, dia):
    abre, fecha = int(loja.abre), int(loja.fecha)
    if loja.loja_id == "L01" and dia >= DATA_MUDANCA_CENTRO:
        abre, fecha = 10, 18
    horas = list(range(abre, fecha))
    tabela = PESO_HORA_ONLINE if loja.canal == "E-commerce" else PESO_HORA_FISICA
    pesos = np.array([tabela[h] for h in horas])
    return horas, pesos / pesos.sum()


def gerar_vendas():
    registros = []
    pedido_seq = 100000
    for d_idx, dia in enumerate(pd.date_range(INICIO, FIM, freq="D")):
        crescimento = 1.08 if dia.year == 2026 else 1.0
        ativos = np.where((cli_inicio <= d_idx) & (cli_fim >= d_idx))[0]
        p_ativos = cli_peso[ativos] / cli_peso[ativos].sum()
        black_friday = dia.month == 11 and 24 <= dia.day <= 30
        for loja in LOJAS.itertuples():
            horas_base, _ = horas_validas(loja._replace(loja_id="X"), dia)  # horário original
            horas, p_horas = horas_validas(loja, dia)
            fator_dia = 1.0 if loja.canal == "E-commerce" else SAZ_DIA[dia.dayofweek]
            esperado = loja.pedidos_dia * SAZ_MES[dia.month] * fator_dia * crescimento
            if black_friday:
                esperado *= 1.8
            # perda de pedidos quando o horário encolhe (só Loja Centro após a mudança)
            tabela = PESO_HORA_FISICA if loja.canal != "E-commerce" else PESO_HORA_ONLINE
            cobertura = sum(tabela[h] for h in horas) / sum(tabela[h] for h in horas_base)
            n_pedidos = rng.poisson(esperado * cobertura)
            for _ in range(n_pedidos):
                pedido_seq += 1
                hora = int(rng.choice(horas, p=p_horas))
                minuto = int(rng.integers(0, 60))
                data_hora = dia + pd.Timedelta(hours=hora, minutes=minuto)
                cli = int(rng.choice(ativos, p=p_ativos))
                n_itens = int(rng.choice([1, 2, 3], p=[0.62, 0.28, 0.10]))
                prods = rng.choice(len(PRODUTOS), n_itens, replace=False, p=peso_prod)
                if loja.canal == "E-commerce":
                    prevista = dia + pd.Timedelta(days=5)
                    atraso = int(rng.choice([-2, -1, 0, 0, 0, 1, 2, 4], p=[.15, .25, .25, .2, .03, .06, .04, .02]))
                    realizada = prevista + pd.Timedelta(days=atraso)
                else:
                    prevista = realizada = pd.NaT
                for p in prods:
                    prod = PRODUTOS.iloc[p]
                    qtd = 1 if prod.categoria == "Eletrônicos" else int(rng.choice([1, 2, 3], p=[.75, .2, .05]))
                    if black_friday:
                        desc = float(rng.choice([10, 15, 20, 25]))
                    else:
                        desc = float(rng.choice([0, 0, 0, 0, 5, 10]))
                    registros.append({
                        "id_pedido": f"PED{pedido_seq}",
                        "data_hora": data_hora,
                        "loja": loja.loja,
                        "canal": loja.canal,
                        "id_produto": prod.produto_id,
                        "quantidade": qtd,
                        "preco_unitario": prod.preco_lista,
                        "desconto_pct": desc,
                        "cliente_nome": cli_nome[cli],
                        "cliente_email": cli_email[cli],
                        "cliente_cidade": cli_cidade[cli],
                        "entrega_prevista": prevista,
                        "entrega_realizada": realizada,
                    })
    return pd.DataFrame(registros)


def sujar(df):
    """Insere problemas reais de qualidade nos dados brutos."""
    df = df.copy()
    n = len(df)
    # datas: formato ISO, mas ~2% no formato brasileiro (dd/mm/aaaa)
    texto = df["data_hora"].dt.strftime("%Y-%m-%d %H:%M")
    br = rng.random(n) < 0.02
    texto[br] = df.loc[br, "data_hora"].dt.strftime("%d/%m/%Y %H:%M")
    df["data_hora"] = texto
    for c in ["entrega_prevista", "entrega_realizada"]:
        df[c] = df[c].dt.strftime("%Y-%m-%d")
    # nomes de loja inconsistentes (~10%)
    idx = rng.random(n) < 0.10
    variantes = {
        "Centro": ["centro", "CENTRO ", "Loja Centro"],
        "Campolim": ["campolim", "Campolim ", "Shopping Campolim"],
        "Éden": ["Eden", "éden", "EDEN"],
        "Votorantim": ["votorantim", "Votorantim ", "Loja Votorantim"],
        "Online": ["online", "E-commerce", "ONLINE"],
    }
    df.loc[idx, "loja"] = [rng.choice(variantes[l]) for l in df.loc[idx, "loja"]]
    # quantidade nula (~0,5%)
    df["quantidade"] = df["quantidade"].astype("float")
    df.loc[rng.random(n) < 0.005, "quantidade"] = np.nan
    # preço zerado ou negativo (~0,3%)
    ruim = rng.random(n) < 0.003
    df.loc[ruim, "preco_unitario"] = rng.choice([0.0, -1.0, -99.9], ruim.sum())
    # produto que não existe no catálogo (~0,2%)
    df.loc[rng.random(n) < 0.002, "id_produto"] = "P999"
    # linhas duplicadas (~0,8%)
    dup = df.sample(frac=0.008, random_state=SEED)
    df = pd.concat([df, dup]).sample(frac=1, random_state=SEED).reset_index(drop=True)
    return df


def gerar_metas(vendas):
    """Meta mensal de receita por loja: 2025 próxima do realizado; 2026 = 2025 + 7%."""
    v = vendas.copy()
    v["receita"] = v["quantidade"] * v["preco_unitario"] * (1 - v["desconto_pct"] / 100)
    v["mes"] = v["data_hora"].dt.to_period("M")
    real = v.groupby(["loja", "mes"])["receita"].sum().reset_index()
    real["ano"] = real["mes"].dt.year
    real["m"] = real["mes"].dt.month
    metas = []
    for r in real.itertuples():
        if r.ano == 2025:
            meta = r.receita * rng.uniform(0.96, 1.06)
        else:
            base = real[(real.loja == r.loja) & (real.ano == 2025) & (real.m == r.m)]["receita"].iloc[0]
            meta = base * 1.07
        metas.append((r.loja, str(r.mes), round(meta, -3)))
    return pd.DataFrame(metas, columns=["loja", "mes", "meta_receita"])


def gerar_tudo():
    PASTA.mkdir(exist_ok=True)
    vendas = gerar_vendas()
    metas = gerar_metas(vendas)
    brutas = sujar(vendas)
    brutas.to_csv(PASTA / "vendas_brutas.csv", index=False, encoding="utf-8")
    PRODUTOS.to_csv(PASTA / "produtos.csv", index=False, encoding="utf-8")
    LOJAS[["loja_id", "loja", "cidade", "canal", "abre", "fecha"]].to_csv(
        PASTA / "lojas.csv", index=False, encoding="utf-8")
    metas.to_csv(PASTA / "metas.csv", index=False, encoding="utf-8")
    print(f"vendas_brutas.csv: {len(brutas):,} linhas")
    print(f"produtos.csv: {len(PRODUTOS)} | lojas.csv: {len(LOJAS)} | metas.csv: {len(metas)}")


if __name__ == "__main__":
    gerar_tudo()
