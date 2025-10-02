import io, zipfile, json
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Finansiell Konsolidering", layout="wide")

st.title("📊 Finansiell Konsolidering (ZIP Loader)")
st.caption("Ladda upp hela txt.zip så läser appen WorkbookSpec, ValidationRules, RR, BR, KF, Mellanhavanden osv.")

# ----------- Helpers -----------

def to_number(x):
    if pd.isna(x): return 0.0
    if isinstance(x, (int, float)): return float(x)
    s = str(x).replace(" ", "").replace(",", ".")
    try: return float(s)
    except: return 0.0

def detect_sep(text):
    # avgör , eller ;
    if text.count(";") > text.count(","):
        return ";"
    return ","

def read_table(data: bytes):
    text = data.decode("utf-8", errors="replace")
    try:
        sep = detect_sep(text)
        return pd.read_csv(io.StringIO(text), sep=sep)
    except:
        return None

# ----------- Upload -----------

uploaded = st.file_uploader("Ladda upp txt.zip", type=["zip"])

tables = {}
workbook_spec = None
validation_rules = None

if uploaded:
    with zipfile.ZipFile(uploaded) as z:
        names = z.namelist()
        for n in names:
            data = z.read(n)
            lname = n.lower()
            if "workbookspec" in lname:
                try:
                    workbook_spec = json.loads(data.decode("utf-8"))
                    st.info("✅ WorkbookSpec hittad")
                except: 
                    st.warning("WorkbookSpec hittades men kunde inte tolkas som JSON.")
            elif "validationrules" in lname:
                try:
                    validation_rules = json.loads(data.decode("utf-8"))
                    st.info("✅ ValidationRules hittad")
                except: 
                    st.warning("ValidationRules hittades men kunde inte tolkas som JSON.")
            elif lname.endswith(".txt"):
                df = read_table(data)
                if df is not None and len(df.columns)>0:
                    tables[n] = df

    st.success(f"Antal tabeller laddade: {len(tables)}")

    # Visa preview
    with st.expander("👀 Förhandsvisning av tabeller"):
        for name, df in tables.items():
            st.write(f"### {name}")
            st.dataframe(df.head(50), use_container_width=True)

    # ----------- Identifiera huvudtabeller -----------
    rr_key = next((k for k in tables if "rr" in k.lower()), None)
    br_key = next((k for k in tables if "br" in k.lower()), None)
    kf_key = next((k for k in tables if "kf" in k.lower()), None)
    ic_key = next((k for k in tables if "mellanhav" in k.lower()), None)

    st.subheader("🔑 Val av huvudtabeller")
    col1,col2,col3,col4 = st.columns(4)
    rr = col1.selectbox("RR-tabell", [None]+list(tables.keys()), index=(list(tables.keys()).index(rr_key)+1 if rr_key in tables else 0))
    br = col2.selectbox("BR-tabell", [None]+list(tables.keys()), index=(list(tables.keys()).index(br_key)+1 if br_key in tables else 0))
    kf = col3.selectbox("KF-tabell", [None]+list(tables.keys()), index=(list(tables.keys()).index(kf_key)+1 if kf_key in tables else 0))
    ic = col4.selectbox("Mellanhavanden", [None]+list(tables.keys()), index=(list(tables.keys()).index(ic_key)+1 if ic_key in tables else 0))

    # ----------- KPI calculation -----------
    st.subheader("📈 KPI-beräkning")
    kpis = {}

    if rr:
        df = tables[rr].copy()
        # försök hitta belopp-kolumn
        belopp_col = None
        for c in df.columns:
            if str(c).strip().lower() in ["belopp","summa","amount"]:
                belopp_col = c; break
        if belopp_col is None and len(df.columns)>2:
            belopp_col = df.columns[2]  # fallback: tredje kolumnen

        if belopp_col:
            df[belopp_col] = df[belopp_col].map(to_number)
            first_col = df.columns[0]
            revenue = df[df[first_col].astype(str).str.contains("RREV", case=False, na=False)][belopp_col].sum()
            ebitda  = df[df[first_col].astype(str).str.contains("REBITDA", case=False, na=False)][belopp_col].sum()
            kpis["Revenue"] = revenue
            kpis["EBITDA"] = ebitda

    if kf:
        df = tables[kf].copy()
        belopp_col = None
        for c in df.columns:
            if str(c).strip().lower() in ["belopp","summa","amount"]:
                belopp_col = c; break
        if belopp_col is None and len(df.columns)>2:
            belopp_col = df.columns[2]

        if belopp_col:
            df[belopp_col] = df[belopp_col].map(to_number)
            first_col = df.columns[0]
            opcf = df[df[first_col].astype(str).str.contains("CFO", case=False, na=False)][belopp_col].sum()
            inv  = df[df[first_col].astype(str).str.contains("CFI", case=False, na=False)][belopp_col].sum()
            fin  = df[df[first_col].astype(str).str.contains("CFF", case=False, na=False)][belopp_col].sum()
            kpis["OpCF"] = opcf
            kpis["InvCF"] = inv
            kpis["FinCF"] = fin
            kpis["NetCF"] = opcf + inv + fin

    if br:
        df = tables[br].copy()
        belopp_col = None
        for c in df.columns:
            if str(c).strip().lower() in ["belopp","summa","amount"]:
                belopp_col = c; break
        if belopp_col is None and len(df.columns)>2:
            belopp_col = df.columns[2]

        if belopp_col:
            df[belopp_col] = df[belopp_col].map(to_number)
            first_col = df.columns[0]
            cash = df[df[first_col].astype(str).str.contains("ACASH", case=False, na=False)][belopp_col].sum()
            debt = df[df[first_col].astype(str).str.contains("LDEBT", case=False, na=False)][belopp_col].sum()
            kpis["Cash"] = cash
            kpis["Debt"] = debt
            kpis["NetDebt"] = debt - cash

    if kpis:
        cols = st.columns(len(kpis))
        for (k,v),c in zip(kpis.items(), cols):
            c.metric(k, f"{v:,.0f}")

    # ----------- Intercompany check -----------
    if ic:
        st.subheader("🔍 Intercompany matchning")
        df = tables[ic].copy()

        # kolumnmatchning
        def find_col(df, candidates):
            cl = {str(c).lower(): c for c in df.columns}
            for cand in candidates:
                if cand.lower() in cl:
                    return cl[cand.lower()]
            # partial
            for c in df.columns:
                for cand in candidates:
                    if cand.lower() in str(c).lower():
                        return c
            return None

        sälj = find_col(df, ["SäljandeBolag","Säljare","Seller"])
        köp  = find_col(df, ["KöpandeBolag","Köpare","Buyer"])
        typ  = find_col(df, ["Typ","Type"])
        val  = find_col(df, ["Valuta","Currency"])
        bel  = find_col(df, ["Belopp","Amount","Summa"])

        if bel: df[bel] = df[bel].map(to_number)
        st.dataframe(df.head(50), use_container_width=True)

        status = "N/A"
        mismatches = []
        if all([sälj, köp, typ, val, bel]):
            from collections import defaultdict
            sums = defaultdict(float)
            for _, r in df.iterrows():
                key = f"{str(r[sälj]).strip()}→{str(r[köp]).strip()}|{str(r[typ]).strip().upper()}|{str(r[val]).strip().upper()}"
                sums[key] += float(r[bel])
            for k, v in list(sums.items()):
                parts = k.split("→")
                rev = parts[1] + "→" + parts[0]
                delta = v + (-sums.get(rev, 0.0))
                if abs(delta) > 1.0:  # tolerans
                    mismatches.append((k, rev, delta))

            status = "MATCHED" if not mismatches else "MISMATCH"

        st.write("**Status:**", status)
        if mismatches:
            st.error(f"Avvikelser: {len(mismatches)}")
            st.dataframe(pd.DataFrame(mismatches, columns=["Key","ReverseKey","Delta"]), use_container_width=True)
        else:
            st.info("Inga avvikelser hittades (inom tolerans ±1).")

    # ----------- Executive Summary -----------
    st.subheader("📝 Executive Summary")
    lang = st.selectbox("Språk / Language", ["sv","ar","en"], index=0)
    if st.button("Generate Summary"):
        rev = kpis.get("Revenue",0)
        ebitda = kpis.get("EBITDA",0)
        netcf = kpis.get("NetCF", kpis.get("OpCF",0))
        netdebt = kpis.get("NetDebt",0)
        if lang=="sv":
            text = f"Översikt: Intäkter {rev:,.0f}, EBITDA {ebitda:,.0f}, NetCF {netcf:,.0f}, Nettoskuld {netdebt:,.0f}."
        elif lang=="ar":
            text = f"نظرة عامة: الإيرادات {rev:,.0f}، EBITDA {ebitda:,.0f}، صافي التدفق {netcf:,.0f}، صافي الدين {netdebt:,.0f}."
        else:
            text = f"Overview: Revenue {rev:,.0f}, EBITDA {ebitda:,.0f}, NetCF {netcf:,.0f}, NetDebt {netdebt:,.0f}."
        st.text_area("Summary", value=text, height=150)
