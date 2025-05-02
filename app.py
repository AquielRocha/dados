# -*- coding: utf-8 -*-
"""
Controle de Gastos — Gastos + Devedores + A Pagar
"""

import streamlit as st, matplotlib.pyplot as plt, pdfplumber, re, sqlite3, unicodedata
from spellchecker import SpellChecker

# ---------------------------------------------------------------- CONFIG -----
st.set_page_config(page_title="Controle de Gastos", layout="wide")

st.markdown(
    """
    <style>
        :root{--pix:#2ecc71;--cred:#3498db;--deb:#e67e22;}
        h1,h2,h3,h4{color:#fafafa;font-weight:600;letter-spacing:.5px;}
        div[data-testid="metric-container"]{
            background:#262730;padding:12px 16px;border-radius:12px;border:1px solid #3a3b43;
        }
        div[data-testid="metric-container"]>div:nth-child(2){font-size:1.4rem;font-weight:700;}
        button[kind="secondary"]{background:#b00020!important;border:none!important;color:#fff!important;}
        button[kind="secondary"]:hover{background:#d32f2f!important;}
        .gasto-row,.dev-row,.pag-row{
            display:flex;justify-content:space-between;align-items:center;
            padding:6px 0;border-bottom:1px dashed #4442;font-size:.93rem;
        }
        .stTabs [data-baseweb="tab-panel"]>div{
            height:72vh;overflow-y:auto;padding-right:6px;
        }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------- DB ---------
conn = sqlite3.connect("controle.db", check_same_thread=False)
cur = conn.cursor()

cur.execute(
    """
    CREATE TABLE IF NOT EXISTS devedores (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        perfil TEXT NOT NULL,
        nome   TEXT NOT NULL,
        valor  REAL NOT NULL
    )
"""
)
cur.execute(
    """
    CREATE TABLE IF NOT EXISTS apagar (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        perfil TEXT NOT NULL,
        nome   TEXT NOT NULL,
        valor  REAL NOT NULL
    )
"""
)
conn_tables = ["devedores", "apagar"]
for tbl in conn_tables:
    try:
        cur.execute(f"ALTER TABLE {tbl} ADD COLUMN perfil TEXT")
    except sqlite3.OperationalError:
        pass
conn = conn  # keep alias

# ------------------------------------------------ PERFIL --------------------
perfil = st.sidebar.selectbox("👤 Perfil", ["Aquiel", "Bruno"])
suf = f"_{perfil.lower()}"

# ------------------------------------------------ HELPERS -------------------
spell = SpellChecker(language="pt")
def corrige(frase):
    s = unicodedata.normalize("NFD", frase)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return " ".join([spell.correction(p).lower() if p not in spell else p.lower() for p in s.split()])

MONEY = r"(\d{1,3}(?:\.\d{3})*(?:,\d{2})?|\d+)"
SKIP  = ["total de","extrato gerado","ouvidoria","atendimento","conta:","metropolitana","agência","agencia"]

def parse(txt):
    txt = corrige(txt).lower()
    m = re.search(MONEY, txt)
    if not m: return
    raw = m.group(1);  raw = raw if "," in raw else f"{raw},00"
    valor = float(raw.replace(".","").replace(",","."))

    if   "pix"    in txt: tp="pix"
    elif "débito" in txt or "debito" in txt: tp="debito"
    elif "crédito" in txt or "credito" in txt: tp="credito"
    else: tp="debito"

    desc = re.sub(r"\b(pix|d[eé]bito|cr[eé]dito)\b","",txt).replace(raw,"").strip(" -–—")
    desc = " ".join(desc.split()) or "(sem descrição)"
    return {"valor":valor,"tipo":tp,"descricao":desc}

# ------------------------------------- SESSION STATE POR PERFIL -------------
for k in ("gastos_pix","gastos_credito","gastos_debito"):
    st.session_state.setdefault(k+suf,[])

# ------------------------------------- LAYOUT PRINCIPAL ---------------------
tab_gastos, tab_dev, tab_pagar = st.tabs(["💸 Gastos", "📝 Devedores", "💳 A Pagar"])

# ================================================= GASTOS ===================
with tab_gastos:
    with st.sidebar:
        st.header("📂 Importar Extrato PDF")
        files = st.file_uploader("Selecione PDFs (Nubank, Itaú)", type="pdf", accept_multiple_files=True)
        if files:
            for f in files:
                with pdfplumber.open(f) as pdf:
                    for p in pdf.pages:
                        for line in (p.extract_text() or "").splitlines():
                            if any(s in line.lower() for s in SKIP): continue
                            g = parse(line)
                            if g:
                                lst = st.session_state[f"gastos_{g['tipo']}{suf}"]
                                if not any(x["valor"]==g["valor"] and x["descricao"]==g["descricao"] for x in lst):
                                    lst.append(g)
            st.success("📥 PDFs importados!")

    cform,cres = st.columns([1,2],gap="medium")

    with cform:
        st.header("📥 Registro Manual")
        with st.form("man",clear_on_submit=True):
            txt = st.text_input('Ex: "500 debito mercado"')
            if st.form_submit_button("Registrar") and txt:
                g=parse(txt)
                if not g: st.error("Sem valor válido.")
                else:
                    lst = st.session_state[f"gastos_{g['tipo']}{suf}"]
                    if any(x["valor"]==g["valor"] and x["descricao"]==g["descricao"] for x in lst):
                        st.warning("Duplicado.")
                    else:
                        lst.append(g); st.success("✅ Registrado!")

    with cres:
        pix  = sum(x["valor"] for x in st.session_state[f"gastos_pix{suf}"])
        cred = sum(x["valor"] for x in st.session_state[f"gastos_credito{suf}"])
        deb  = sum(x["valor"] for x in st.session_state[f"gastos_debito{suf}"])
        tot  = pix+cred+deb

        st.header("💰 Resumo")
        m1,m2,m3,m4 = st.columns(4)
        m1.metric("PIX",f"R$ {pix:.2f}")
        m2.metric("Crédito",f"R$ {cred:.2f}")
        m3.metric("Débito",f"R$ {deb:.2f}")
        m4.metric("Total",f"R$ {tot:.2f}")

        st.subheader("Distribuição (%)")
        if tot:
            fig,ax=plt.subplots()
            ax.pie([pix,cred,deb],labels=["PIX","Crédito","Débito"],
                   colors=["#2ecc71","#3498db","#e67e22"],autopct="%1.1f%%",startangle=90)
            ax.axis("equal"); st.pyplot(fig,use_container_width=True)

    st.markdown("### 🗑️ / 📋 Detalhes e Ações")
    for cat,key in [("PIX",f"gastos_pix{suf}"),("Crédito",f"gastos_credito{suf}"),("Débito",f"gastos_debito{suf}")]:
        st.markdown(f"#### {cat}")
        for i,g in enumerate(st.session_state[key]):
            st.markdown(f"""
            <div class="gasto-row"><span>{g['descricao']}</span><span>R$ {g['valor']:.2f}</span>
            <span><form action="#" method="post">
            <button kind="secondary" name="del" value="{key}_{i}">❌</button></form></span></div>""",unsafe_allow_html=True)
            if st.query_params.get("del")==f"{key}_{i}":
                st.session_state[key].pop(i); st.experimental_set_query_params(); st.rerun()

# =============================================== DEVEDORES ==================
with tab_dev:
    st.header("📝 Quem Me Deve")
    with st.form("add_dev",clear_on_submit=True):
        nome = st.text_input("Nome do Devedor")
        valor= st.number_input("Valor devido (R$)",min_value=0.0,format="%.2f")
        if st.form_submit_button("Adicionar"):
            if not nome or valor<=0: st.error("Preencha direito.")
            else:
                cur.execute("INSERT INTO devedores(perfil,nome,valor) VALUES (?,?,?)",
                            (perfil,nome,valor)); conn.commit()
                st.success("Devedor adicionado!")

    st.subheader("Lista")
    devs = cur.execute("SELECT id,nome,valor FROM devedores WHERE perfil=?",(perfil,)).fetchall()
    for id_,n,v in devs:
        st.markdown(f"""
        <div class="dev-row"><span>{n}</span><span>R$ {v:.2f}</span>
        <span><form action="#" method="post">
        <button kind="secondary" name="deldev" value="{id_}">❌</button></form></span></div>""",unsafe_allow_html=True)
        if st.query_params.get("deldev")==str(id_):
            cur.execute("DELETE FROM devedores WHERE id=?",(id_,)); conn.commit()
            st.experimental_set_query_params(); st.rerun()

# ================================================ A PAGAR ====================
with tab_pagar:
    st.header("💳 Contas a Pagar")
    with st.form("add_pag",clear_on_submit=True):
        nome_pg = st.text_input("Quem você deve pagar?")
        valor_pg= st.number_input("Valor (R$)",min_value=0.0,format="%.2f", key="valor_pagar")
        if st.form_submit_button("Adicionar"):
            if not nome_pg or valor_pg<=0: st.error("Preencha tudo certinho.")
            else:
                cur.execute("INSERT INTO apagar(perfil,nome,valor) VALUES (?,?,?)",
                            (perfil,nome_pg,valor_pg)); conn.commit()
                st.success("Conta a pagar adicionada!")

    st.subheader("Lista de Contas Pendentes")
    a_pagar = cur.execute("SELECT id,nome,valor FROM apagar WHERE perfil=?",(perfil,)).fetchall()
    for id_,n,v in a_pagar:
        st.markdown(f"""
        <div class="pag-row"><span>{n}</span><span>R$ {v:.2f}</span>
        <span><form action="#" method="post">
        <button kind="secondary" name="delpag" value="{id_}">❌</button></form></span></div>""",unsafe_allow_html=True)
        if st.query_params.get("delpag")==str(id_):
            cur.execute("DELETE FROM apagar WHERE id=?",(id_,)); conn.commit()
            st.set_query_params(); st.rerun()
