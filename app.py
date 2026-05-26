import streamlit as st
import pandas as pd
import re
import asyncio
from PIL import Image
from openpyxl import Workbook
from openai import AsyncOpenAI
import google.generativeai as genai


# =========================
# CONFIG API KEYS
# =========================
GEMINI_API = st.secrets["GEMINI_API"]
OPENROUTER_API = st.secrets["OPENROUTER_API"]

# CLIENTES
client_gemini = genai.configure(api_key=GEMINI_API)

client_or = AsyncOpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_API,
)

# =========================
# FUNÇÕES AUXILIARES
# =========================

def buscar_valor(campo, texto):
    match = re.search(rf"{campo}:\s*(.*)", texto)
    return match.group(1).strip() if match else "N/A"


def extrair_confianca(texto):
    valor = buscar_valor("CONFIANÇA", texto)
    try:
        return int(re.sub(r"\D", "", valor))
    except:
        return 0


def escolher_melhor(respostas):
    validas = {r: extrair_confianca(r) for r in respostas if r}
    if not validas:
        return None, 0

    melhor = max(validas, key=validas.get)
    return melhor, validas[melhor]


# =========================
# CHAMADAS À IA
# =========================

async def chamar_openrouter(prompt):
    try:
        response = await client_or.chat.completions.create(
            model="openrouter/free",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=600,
        )
        return response.choices[0].message.content
    except:
        return None


async def chamar_gemini(prompt, imagem=None):
    try:
        if imagem:
            res = genai.GenerativeModel("gemini-1.5-flash").generate_content(
                model="models/gemini-1.5-flash",
                contents=[prompt, imagem]
            )
        else:
            res = genai.GenerativeModel("gemini-1.5-flash").generate_content(

                model="models/gemini-1.5-flash",
                contents=prompt
            )
        return res.text
    except:
        return None


# =========================
# ANÁLISE PRINCIPAL
# =========================

async def analisar_com_ia(conteudo, imagem=None):

    prompt = f"""
Tu és um Engenheiro de Manutenção Especialista.

Analisa o relatório:

{conteudo}

Responde apenas neste formato:

--------------------------------------------------
ID:
DATA:
RESPONSÁVEL:
EQUIPAMENTO:
MODELO:
DIAGNÓSTICO:
SOLUÇÃO:
GRAVIDADE:
CONFIANÇA:
--------------------------------------------------
"""

    tarefa1 = chamar_gemini(prompt, imagem)
    tarefa2 = chamar_openrouter(prompt)
    tarefa3 = chamar_openrouter(prompt)

    r1, r2, r3 = await asyncio.gather(tarefa1, tarefa2, tarefa3)

    melhor, conf = escolher_melhor([r1, r2, r3])

    return melhor, conf, r1, r2, r3


# =========================
# EXCEL
# =========================

def criar_excel(texto, confianca):
    wb = Workbook()
    ws = wb.active

    ws['A1'] = "RELATÓRIO AUTOMÁTICO"

    ws['A3'] = "ID"
    ws['B3'] = buscar_valor("ID", texto)

    ws['A4'] = "DATA"
    ws['B4'] = buscar_valor("DATA", texto)

    ws['A5'] = "RESPONSÁVEL"
    ws['B5'] = buscar_valor("RESPONSÁVEL", texto)

    ws['A6'] = "EQUIPAMENTO"
    ws['B6'] = buscar_valor("EQUIPAMENTO", texto)

    ws['A7'] = "MODELO"
    ws['B7'] = buscar_valor("MODELO", texto)

    ws['A9'] = "DIAGNÓSTICO"
    ws['B9'] = buscar_valor("DIAGNÓSTICO", texto)

    ws['A12'] = "SOLUÇÃO"
    ws['B12'] = buscar_valor("SOLUÇÃO", texto)

    ws['A15'] = "GRAVIDADE"
    ws['B15'] = buscar_valor("GRAVIDADE", texto)

    ws['A16'] = "CONFIANÇA"
    ws['B16'] = f"{confianca}%"

    file_path = "resultado.xlsx"
    wb.save(file_path)

    return file_path


# =========================
# INTERFACE
# =========================

st.set_page_config(page_title="IA Manutenção", layout="centered")

st.title("🤖 Sistema Inteligente de Avarias (IA Real)")

ficheiro = st.file_uploader(
    "Carregar relatório",
    type=["xlsx", "xls", "png", "jpg", "jpeg", "docx"]
)

if ficheiro:
    st.success("Ficheiro carregado ✅")

if st.button("🔍 Analisar com IA"):
    if not ficheiro:
        st.warning("Carrega primeiro um ficheiro")
    else:
        with st.spinner("A analisar com múltiplas IAs..."):

            conteudo = ""
            imagem = None

            # Excel
            if ficheiro.name.endswith((".xlsx", ".xls")):
                df = pd.read_excel(ficheiro)
                conteudo = df.to_string()

            # Imagem
            elif ficheiro.name.endswith((".png", ".jpg", ".jpeg")):
                imagem = Image.open(ficheiro)
                st.image(imagem)
                conteudo = "Relatório em imagem"

            # Word
            elif ficheiro.name.endswith(".docx"):
                import docx
                doc = docx.Document(ficheiro)
                conteudo = "\n".join([p.text for p in doc.paragraphs])

            # EXECUTA IA
            resultado, conf, r1, r2, r3 = asyncio.run(
                analisar_com_ia(conteudo, imagem)
            )

            # RESULTADOS
            st.subheader("📊 Melhor Resultado")
            st.code(resultado if resultado else "Sem resposta")

            st.write(f"✅ Confiança escolhida: **{conf}%**")

            with st.expander("Ver respostas das IAs"):
                st.write("Gemini:")
                st.code(r1)

                st.write("OpenRouter A:")
                st.code(r2)

                st.write("OpenRouter B:")
                st.code(r3)

            # Excel
            if resultado:
                path = criar_excel(resultado, conf)

                with open(path, "rb") as f:
                    st.download_button(
                        "⬇️ Download Excel",
                        f,
                        file_name="relatorio_final.xlsx"
                    )
