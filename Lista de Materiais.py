# COMANDO PARA GERAR O EXECUTÁVEL:
# python -m PyInstaller --noconsole --onefile --name "Lista de Materiais" "Lista de Materiais.py"

import zipfile
import os
import shutil
import xml.etree.ElementTree as ET
import sys
import csv
import math 
import re
from geopy.distance import geodesic
from collections import defaultdict
from tkinter import Tk, filedialog, Button, Label, END, ttk, Frame, Entry, Canvas, IntVar, Checkbutton
from tkinter.scrolledtext import ScrolledText
import tkinter.messagebox as messagebox

# ==============================================================================
# 1. CONFIGURAÇÕES VISUAIS E TÉCNICAS
# ==============================================================================

GIGA_AZUL       = "#005EB8"
GIGA_VERDE      = "#E0E721"
GIGA_BRANCO     = "#FFFFFF"
GIGA_CINZA_BG   = "#F4F7F6"
GIGA_CINZA_TXT  = "#555555"
GIGA_PRETO      = "#333333"

MAPA_CABOS = {
    "#00FF00": "Cabo 6 FO",    "#0000FF": "Cabo 12 FO",   "#00FFFF": "Cabo 12 FO",
    "#FF0000": "Cabo 24 FO",   "#FF5500": "Cabo 36 FO",   "#FFA500": "Cabo 36 FO",
    "#00008B": "Cabo 48 FO",   "#FFFF00": "Cabo 72 FO",   "#000000": "Cabo 144 FO"
}

ICON_LINK_0       = "http://maps.google.com/mapfiles/kml/shapes/polygon.png"
ICON_RESERVA_BOLA = "http://maps.google.com/mapfiles/kml/shapes/target.png"
ICON_PUSHPIN      = "ylw-pushpin.png"

PRECOS_PADRAO = {
    "Cabo 6 FO": 1.90, "Cabo 12 FO": 2.28, "Cabo 24 FO": 2.90, "Cabo 36 FO": 3.75,
    "Cabo 48 FO": 6.20, "Cabo 72 FO": 8.81, "Cabo 144 FO": 14.50, "Outros Cabos": 1.00,
    "CTO 1x4": 130.00, "CTO 1x8": 149.00, "CTO 1x16": 159.00, 
    "CTO 1x4 CEIP": 130.00, "Splitter 1x4 (c/ Conector)": 45.00, # Novos Itens adicionados
    "CEO (Emenda)": 210.00, "HUB": 210.00,
    "Splitter 1x2 (s/ Conector)": 28.45, "Splitter 1x4 (s/ Conector)": 32.63,
    "Splitter 1x8 (s/ Conector)": 49.99, "Splitter 1x16 (s/ Conector)": 43.38,
    "Alça 6/12 FO": 2.24, "Alça 24 FO": 4.19, "Alça 36 FO": 5.80,
    "Alça 48 FO": 6.10, "Alça 72 FO": 8.00, "Alça 144 FO": 12.00,
    "Kit Derivação": 19.38, "Bandeja CEO": 19.69,
    "Anel Guia": 0.59, "Plaquetas": 0.90, "Abraçadeira BAP": 5.05, 
    "Bracket": 12.00, "BAP 3 c/ Parafuso": 5.20, "Fixação Extra": 5.00
}

dados_exportacao = [] 
entradas_preco = {}

# ==============================================================================
# 2. FUNÇÕES AUXILIARES
# ==============================================================================

def log(texto, cor="black"):
    try:
        janela_debug.insert(END, texto + "\n")
        if cor == "red":
            janela_debug.tag_add("erro", "end-2c linestart", "end-1c")
            janela_debug.tag_config("erro", foreground="red", font=("Consolas", 9, "bold"))
        janela_debug.see(END)
    except: pass

def strip_ns(tag):
    return tag.split('}', 1)[1] if '}' in tag else tag

def get_preco(item_nome):
    try:
        if item_nome in entradas_preco:
            return float(entradas_preco[item_nome].get().replace(",", ".").strip())
        return PRECOS_PADRAO.get(item_nome, 0.0)
    except: return 0.0

def kml_to_hex(c): 
    return f"#{c[6:8]}{c[4:6]}{c[2:4]}".upper() if c and len(c)==8 else None

def salvar():
    f = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV", "*.csv")])
    if f:
        with open(f, 'w', newline='', encoding='utf-8-sig') as file:
            csv.writer(file, delimiter=';').writerows(dados_exportacao)
        messagebox.showinfo("Sucesso", "Salvo!")

def get_inline_style(pm_element):
    d = {"color": None, "icon": None, "icon_color": None}
    for c in pm_element:
        if strip_ns(c.tag) == "Style":
            for g in c.iter():
                tag = strip_ns(g.tag)
                if tag == "LineStyle":
                    for h in g.iter(): 
                        if strip_ns(h.tag) == "color": d["color"] = h.text.strip()
                if tag == "IconStyle":
                    for h in g.iter():
                        if strip_ns(h.tag) == "color": d["icon_color"] = h.text.strip()
                        if strip_ns(h.tag) == "Icon":
                            for i in h.iter(): 
                                if strip_ns(i.tag) == "href": d["icon"] = i.text.strip()
    return d

def resolver_estilo_referencia(style_url, style_map, pair_map):
    if not style_url: return None
    style_url = style_url.strip()
    if style_url in pair_map: style_url = pair_map[style_url]
    return style_map.get(style_url)

# ==============================================================================
# 3. LÓGICA DE PROCESSAMENTO
# ==============================================================================

def analisar_kmz():
    global dados_exportacao
    dados_exportacao = []
    janela_debug.delete(1.0, END)
    tipo_splitter_dropdown = combo_splitter.get()
    tem_estrutura = var_estrutura.get() == 1
    
    nav_to_report()
    lbl_status.config(text="Processando...", fg=GIGA_AZUL); root.update()

    kmz_path = filedialog.askopenfilename(title="Selecione o KMZ", filetypes=[("Arquivos KMZ", "*.kmz")])
    if not kmz_path:
        lbl_status.config(text="Cancelado.", fg="red"); nav_to_home(); return

    temp_dir = os.path.join(os.path.dirname(__file__), "temp_orcamento")
    if os.path.exists(temp_dir): shutil.rmtree(temp_dir)
    os.makedirs(temp_dir)

    try:
        with zipfile.ZipFile(kmz_path, "r") as z: z.extractall(temp_dir)
        kml_files = [os.path.join(temp_dir, f) for f in os.listdir(temp_dir) if f.endswith(".kml")]
        
        cabos_resumo = defaultdict(float)
        equip = defaultdict(int)
        extras = defaultdict(int)
        reserva_extra_marcadores = 0.0 
        acumulador_bandejas_extras = 0 
        soma_metragem_absoluta = 0.0 

        log(f"--- RASTREAMENTO GIGALINK V70.20 ---")

        for kml in kml_files:
            tree = ET.parse(kml); root_iter = tree.getroot()
            style_map, pair_map = {}, {}
            for elem in root_iter.iter():
                tag = strip_ns(elem.tag)
                if tag == "Style":
                    sid = elem.attrib.get("id"); sid = "#" + sid if sid else None
                    if sid:
                        style_map[sid] = {"color": None, "icon": None}
                        for child in elem.iter():
                            if strip_ns(child.tag) == "LineStyle":
                                for g in child.iter(): 
                                    if strip_ns(g.tag)=="color": style_map[sid]["color"]=g.text.strip()
                            if strip_ns(child.tag) == "IconStyle":
                                for g in child.iter():
                                    if strip_ns(g.tag)=="Icon":
                                        for h in g.iter(): 
                                            if strip_ns(h.tag)=="href": style_map[sid]["icon"]=h.text.strip()
                                    if strip_ns(g.tag)=="color": style_map[sid]["icon_color"]=g.text.strip()
                if tag == "StyleMap":
                    sid = elem.attrib.get("id"); sid = "#" + sid if sid else None
                    if sid:
                        for pair in elem.iter():
                            if strip_ns(pair.tag)=="Pair":
                                key, url = None, None
                                for c in pair.iter():
                                    if strip_ns(c.tag)=="key": key=c.text
                                    if strip_ns(c.tag)=="styleUrl": url=c.text.strip()
                                if key=="normal" and url: pair_map[sid]=url

            for pm in root_iter.iter():
                if strip_ns(pm.tag) == "Placemark":
                    name = pm.findtext('.//{http://www.opengis.net/kml/2.2}name')
                    style_url = pm.findtext('.//{http://www.opengis.net/kml/2.2}styleUrl')
                    nm = name.strip() if name else "SEM NOME"
                    nm_c_upper = nm.upper().replace(" ", "")
                    dados_estilo = get_inline_style(pm)
                    if not dados_estilo.get("color") and style_url:
                        resolved = resolver_estilo_referencia(style_url, style_map, pair_map)
                        if resolved: dados_estilo.update(resolved)

                    line = pm.find('.//{http://www.opengis.net/kml/2.2}LineString')
                    if line is not None:
                        coords = line.findtext('{http://www.opengis.net/kml/2.2}coordinates')
                        if coords:
                            pts = []
                            for co in coords.strip().split():
                                p = co.split(","); pts.append((float(p[1]), float(p[0])))
                            if len(pts)>=2:
                                d = sum(geodesic(pts[i], pts[i+1]).meters for i in range(len(pts)-1))
                                soma_metragem_absoluta += d
                                hex_c = kml_to_hex(dados_estilo.get("color"))
                                tipo = MAPA_CABOS.get(hex_c)
                                if tipo:
                                    cabos_resumo[tipo] += d
                                else:
                                    cabos_resumo["Outros Cabos"] += d

                    point = pm.find('.//{http://www.opengis.net/kml/2.2}Point')
                    if point is not None:
                        href = dados_estilo.get("icon", "")
                        icol = kml_to_hex(dados_estilo.get("icon_color", ""))
                        if not href or ICON_PUSHPIN in href or icol == "#FFFF00": continue
                        if ICON_RESERVA_BOLA in href:
                            reserva_extra_marcadores += 20.0; log(f"⭕ Reserva Técnica: {nm} (+20m)"); continue

                        # --- DETECÇÃO CEIP / CTOs ---
                        if "CEIP" in nm_c_upper:
                            if "1:4" in nm_c_upper or "1X4" in nm_c_upper:
                                equip["CTO 1x4 CEIP"] += 1
                                extras["Splitter 1x4 (c/ Conector)"] += 1  
                            elif "1:8" in nm_c_upper or "1X8" in nm_c_upper:
                                equip["CTO 1x8"] += 1  
                            elif "1:16" in nm_c_upper or "1X16" in nm_c_upper:
                                equip["CTO 1x16"] += 1
                        else:
                            if "GP1:4" in nm_c_upper: equip["CTO 1x4"] += 1
                            elif "GP1:8" in nm_c_upper: equip["CTO 1x8"] += 1
                            elif "GP1:16" in nm_c_upper: equip["CTO 1x16"] += 1

                        if ICON_LINK_0 in href:
                            partes = [p.strip() for p in nm.split("-")]
                            if "HUB" in nm_c_upper:
                                equip["HUB"] += 1
                                log(f"📦 HUB Encontrado: {nm}")
                                
                                if len(partes) >= 4:
                                    splitagem = partes[1].upper()
                                    kit_texto = partes[2].upper()
                                    bandeja_texto = partes[3].upper()

                                    if "1:2" in splitagem or "1X2" in splitagem: extras["Splitter 1x2 (s/ Conector)"] += 1
                                    elif "1:4" in splitagem or "1X4" in splitagem: extras["Splitter 1x4 (s/ Conector)"] += 1
                                    elif "1:8" in splitagem or "1X8" in splitagem: extras["Splitter 1x8 (s/ Conector)"] += 1
                                    elif "1:16" in splitagem or "1X16" in splitagem: extras["Splitter 1x16 (s/ Conector)"] += 1
                                    else: extras["Splitter_Padrao"] += 1

                                    num_cabos = re.findall(r'\d+', kit_texto)
                                    if num_cabos:
                                        extras["Kit Derivação"] += int(num_cabos[0])

                                    num_bandejas = re.findall(r'\d+', bandeja_texto)
                                    if num_bandejas:
                                        acumulador_bandejas_extras += int(num_bandejas[0])

                                    # --- NOVA LÓGICA: DETECÇÃO DE SAÍDAS E RESERVA DA HUB ---
                                    if len(partes) >= 5:
                                        dados_saida = partes[4].upper() 
                                        if "_" in dados_saida:
                                            qtd_saidas_txt, tipo_cabo_txt = dados_saida.split("_", 1)
                                            try:
                                                qtd_saidas = int(re.findall(r'\d+', qtd_saidas_txt)[0])
                                                cabo_destino = None
                                                if "6FO" in tipo_cabo_txt:   cabo_destino = "Cabo 6 FO"
                                                elif "12FO" in tipo_cabo_txt: cabo_destino = "Cabo 12 FO"
                                                elif "24FO" in tipo_cabo_txt: cabo_destino = "Cabo 24 FO"
                                                elif "36FO" in tipo_cabo_txt: cabo_destino = "Cabo 36 FO"
                                                elif "48FO" in tipo_cabo_txt: cabo_destino = "Cabo 48 FO"
                                                elif "72FO" in tipo_cabo_txt: cabo_destino = "Cabo 72 FO"
                                                elif "144FO" in tipo_cabo_txt: cabo_destino = "Cabo 144 FO"

                                                if cabo_destino:
                                                    metragem_reserva_hub = qtd_saidas * 15.0
                                                    cabos_resumo[cabo_destino] += metragem_reserva_hub
                                                    log(f"   ↳ 🔌 Reserva HUB: {qtd_saidas} saída(s) de {cabo_destino} (+{metragem_reserva_hub}m)")
                                            except Exception as err:
                                                log(f"⚠️ Erro ao processar saídas da HUB '{nm}': {err}", "red")
                                else:
                                    log(f"⚠️ [Aviso] HUB fora do padrão 'HUB-Splitagem-Kit-Bandeja': {nm}", "red")
                                    extras["Splitter_Padrao"] += 1
                                    extras["Kit Derivação"] += 1
                                    acumulador_bandejas_extras += 1
                            else:
                                # --- LÓGICA ATUALIZADA DA CEO ---
                                if "GP1:" not in nm_c_upper and "CEIP" not in nm_c_upper:
                                    equip["CEO"] += 1
                                    log(f"📦 CEO Encontrada: {nm}")
                                    try:
                                        if len(partes) >= 2: extras["Kit Derivação"] += int(partes[1].strip().upper().replace("D",""))
                                        if len(partes) >= 3: 
                                            bandeja_limpa = partes[2].strip().upper().split("_")[0].replace("B","").replace(" ","")
                                            acumulador_bandejas_extras += int(bandeja_limpa)
                                        
                                        # --- NOVA LÓGICA: DETECÇÃO DE SAÍDAS E RESERVA DA CEO ---
                                        if len(partes) >= 4:
                                            dados_saida_ceo = partes[3].upper() 
                                            if "_" in dados_saida_ceo:
                                                qtd_saidas_txt, tipo_cabo_txt = dados_saida_ceo.split("_", 1)
                                                qtd_saidas = int(re.findall(r'\d+', qtd_saidas_txt)[0])
                                                
                                                cabo_destino = None
                                                if "6FO" in tipo_cabo_txt:   cabo_destino = "Cabo 6 FO"
                                                elif "12FO" in tipo_cabo_txt: cabo_destino = "Cabo 12 FO"
                                                elif "24FO" in tipo_cabo_txt: cabo_destino = "Cabo 24 FO"
                                                elif "36FO" in tipo_cabo_txt: cabo_destino = "Cabo 36 FO"
                                                elif "48FO" in tipo_cabo_txt: cabo_destino = "Cabo 48 FO"
                                                elif "72FO" in tipo_cabo_txt: cabo_destino = "Cabo 72 FO"
                                                elif "144FO" in tipo_cabo_txt: cabo_destino = "Cabo 144 FO"

                                                if cabo_destino:
                                                    metragem_reserva_ceo = qtd_saidas * 15.0
                                                    cabos_resumo[cabo_destino] += metragem_reserva_ceo
                                                    log(f"   ↳ 🔌 Reserva CEO: {qtd_saidas} saída(s) de {cabo_destino} (+{metragem_reserva_ceo}m)")
                                    except Exception as err: 
                                        log(f"⚠️ Erro ao processar dados da CEO '{nm}': {err}", "red")

        # --- CÁLCULOS FINAIS COM AS REGRAS ---
        ctos_total = equip["CTO 1x4"] + equip["CTO 1x8"] + equip["CTO 1x16"] + equip["CTO 1x4 CEIP"]
        reserva_total = (ctos_total * 20.0) + reserva_extra_marcadores
        qtd_anel_guia = ctos_total * 2

        m_6_12 = cabos_resumo["Cabo 6 FO"] + cabos_resumo["Cabo 12 FO"] + reserva_total
        alca_6_12 = math.ceil((m_6_12 / 100) * 6) if m_6_12 > 0 else 0
        
        alca_24 = math.ceil((cabos_resumo["Cabo 24 FO"] / 100) * 6) if cabos_resumo["Cabo 24 FO"] > 0 else 0
        alca_36 = math.ceil((cabos_resumo["Cabo 36 FO"] / 100) * 6) if cabos_resumo["Cabo 36 FO"] > 0 else 0
        alca_48 = math.ceil((cabos_resumo["Cabo 48 FO"] / 100) * 6) if cabos_resumo["Cabo 48 FO"] > 0 else 0
        alca_72 = math.ceil((cabos_resumo["Cabo 72 FO"] / 100) * 6) if cabos_resumo["Cabo 72 FO"] > 0 else 0
        alca_144 = math.ceil((cabos_resumo["Cabo 144 FO"] / 100) * 6) if cabos_resumo["Cabo 144 FO"] > 0 else 0

        qtd_brk = 0 if tem_estrutura else math.ceil((soma_metragem_absoluta/100)*3)
        
        bap3_cto_1x4 = equip["CTO 1x4"]
        qtd_bap3 = (equip["CTO 1x8"] + equip["CTO 1x16"] + bap3_cto_1x4) + qtd_brk

        itens = []
        for t in ["Cabo 6 FO", "Cabo 12 FO", "Cabo 24 FO", "Cabo 36 FO", "Cabo 48 FO", "Cabo 72 FO", "Cabo 144 FO"]:
            if cabos_resumo[t] > 0: itens.append((t, cabos_resumo[t], "m", get_preco(t)))
        itens.append(("Reserva Técnica (Cabo 6FO)", reserva_total, "m", get_preco("Cabo 6 FO")))

        chaves_equip = ["CTO 1x4", "CTO 1x4 CEIP", "CTO 1x8", "CTO 1x16", "CEO", "HUB"]
        for k in chaves_equip:
            q = equip[k]
            nome_exib = "CEO (Emenda)" if k == "CEO" else k
            if q > 0: 
                chave_preco = "CTO 1x4" if k == "CTO 1x4 CEIP" else nome_exib
                itens.append((nome_exib, q, "un", get_preco(chave_preco)))

        if alca_6_12 > 0: itens.append(("Alça 6/12 FO", alca_6_12, "un", get_preco("Alça 6/12 FO")))
        if alca_24 > 0:   itens.append(("Alça 24 FO", alca_24, "un", get_preco("Alça 24 FO")))
        if alca_36 > 0:   itens.append(("Alça 36 FO", alca_36, "un", get_preco("Alça 36 FO")))
        if alca_48 > 0:   itens.append(("Alça 48 FO", alca_48, "un", get_preco("Alça 48 FO")))
        if alca_72 > 0:   itens.append(("Alça 72 FO", alca_72, "un", get_preco("Alça 72 FO")))
        if alca_144 > 0:  itens.append(("Alça 144 FO", alca_144, "un", get_preco("Alça 144 FO")))

        if acumulador_bandejas_extras > 0: itens.append(("Bandeja CEO", acumulador_bandejas_extras, "un", get_preco("Bandeja CEO")))
        if qtd_anel_guia > 0: itens.append(("Anel Guia", qtd_anel_guia, "un", get_preco("Anel Guia")))
        
        for k, v in extras.items():
            if k == "Splitter_Padrao" and v > 0:
                itens.append((f"Splitter {tipo_splitter_dropdown} (s/ Conector)", v, "un", get_preco(f"Splitter {tipo_splitter_dropdown} (s/ Conector)")))
            elif v > 0: itens.append((k, v, "un", get_preco(k)))

        for n, q in [("Plaquetas", math.ceil(soma_metragem_absoluta/50)), ("Abraçadeira BAP", ctos_total*4), ("Bracket", qtd_brk), ("BAP 3 c/ Parafuso", qtd_bap3)]:
            if q > 0: itens.append((n, q, "un", get_preco(n)))

        # --- EXIBIÇÃO ---
        total_p = 0.0
        dados_exportacao.append(["ITEM", "QUANTIDADE", "UNIDADE", "TOTAL"])
        log("\n--- ORÇAMENTO V70.20 (REGRAS DE ALÇAS ATUALIZADAS) ---")
        for nm_item, q_item, un, pr in itens:
            tot = q_item * pr; total_p += tot
            log(f"{nm_item:<30} | {q_item:>8.2f} {un} | R$ {tot:>10.2f}")
            dados_exportacao.append([nm_item, f"{q_item:.2f}".replace(".",","), un, f"{tot:.2f}".replace(".",",")])
        lbl_status.config(text=f"Total: R$ {total_p:,.2f}", fg=GIGA_AZUL)

    except Exception as e: messagebox.showerror("Erro", f"Ocorreu um erro: {e}")
    finally:
        if os.path.exists(temp_dir): shutil.rmtree(temp_dir)

# ==============================================================================
# 4. UI SETUP
# ==============================================================================

class RoundedButton(Canvas):
    def __init__(self, parent, text, command, width=220, height=45, radius=22, bg_color=GIGA_AZUL, fg_color="white"):
        super().__init__(parent, width=width, height=height, bg=parent["bg"], highlightthickness=0)
        self.command = command; self.bg = bg_color; self.fg = fg_color
        self.rect = self.create_rounded_rect(0, 0, width, height, radius, bg_color)
        self.text_item = self.create_text(width/2, height/2, text=text, fill=fg_color, font=("Segoe UI", 10, "bold"))
        self.bind("<Button-1>", lambda e: command())
        self.bind("<Enter>", lambda e: self.itemconfig(self.rect, fill="#004C99"))
        self.bind("<Leave>", lambda e: self.itemconfig(self.rect, fill=self.bg))
    def create_rounded_rect(self, x1, y1, x2, y2, r, color):
        p = [x1+r, y1, x1+r, y1, x2-r, y1, x2-r, y1, x2, y1, x2, y1+r, x2, y1+r, x2, y2-r, x2, y2-r, x2, y2, x2-r, y2, x2-r, y2, x1+r, y2, x1+r, y2, x1, y2, x1, y2-r, x1, y2-r, x1, y1+r, x1, y1+r, x1, y1]
        return self.create_polygon(p, smooth=True, fill=color)
    def set_active(self, active=True):
        c = GIGA_AZUL if active else "white"; t = "white" if active else GIGA_AZUL
        self.itemconfig(self.rect, fill=c); self.itemconfig(self.text_item, fill=t); self.bg = c

class RoundedFrame(Canvas):
    def __init__(self, parent, width, height):
        super().__init__(parent, width=width, height=height, bg=parent["bg"], highlightthickness=0)
        p = [30,0, width-30,0, width,30, width,height-30, width-30,height, 30,height, 0,height-30, 0,30]
        self.create_polygon(p, smooth=True, fill="white", outline="#E0E0E0")
        self.inner = Frame(self, bg="white"); self.create_window(width/2, height/2, window=self.inner, width=width-40, height=height-40)

root = Tk(); root.title("GIGALINK - Orçamento V70.20"); root.geometry("850x750"); root.configure(bg=GIGA_CINZA_BG)

header = Frame(root, bg="white", height=80); header.pack(fill="x"); header.pack_propagate(False)
Label(header, text="gigalink", font=("Arial", 30, "bold"), bg="white", fg=GIGA_AZUL).pack(side="left", padx=30)
nav = Frame(root, bg=GIGA_CINZA_BG, height=70); nav.pack(fill="x", padx=40, pady=20)
content = Frame(root, bg=GIGA_CINZA_BG); content.pack(fill="both", expand=True)
view_home = Frame(content, bg=GIGA_CINZA_BG); view_prices = Frame(content, bg=GIGA_CINZA_BG); view_log = Frame(content, bg=GIGA_CINZA_BG)

def show_view(v, b):
    for x in [view_home, view_prices, view_log]: x.place_forget()
    v.place(relx=0.5, rely=0.5, anchor="center", width=750, height=550)
    for x in [btn_h, btn_p, btn_l]: x.set_active(False)
    b.set_active(True)

def nav_to_home(): show_view(view_home, btn_h)
def nav_to_report(): show_view(view_log, btn_l)

btn_h = RoundedButton(nav, "INÍCIO", nav_to_home, 160); btn_h.pack(side="left", padx=10)
btn_p = RoundedButton(nav, "PREÇOS", lambda: show_view(view_prices, btn_p), 200); btn_p.pack(side="left", padx=10)
btn_l = RoundedButton(nav, "RELATÓRIO", nav_to_report, 160); btn_l.pack(side="left", padx=10)

# HOME
home_card = RoundedFrame(view_home, 650, 480); home_card.place(relx=0.5, rely=0.5, anchor="center")
Label(home_card.inner, text="ORÇAMENTO GPON", font=("Segoe UI", 20, "bold"), bg="white", fg=GIGA_AZUL).pack(pady=20)
f_c = Frame(home_card.inner, bg="white"); f_c.pack(pady=10)
Label(f_c, text="SPLITTER HUB:", font=("Segoe UI", 10, "bold"), bg="white").grid(row=0, column=0, padx=10)
combo_splitter = ttk.Combobox(f_c, values=["1x2", "1x4", "1x8", "1x16"], state="readonly", width=15); combo_splitter.current(3); combo_splitter.grid(row=0, column=1)
var_estrutura = IntVar(); 
Checkbutton(home_card.inner, text="Infraestrutura já existe?", variable=var_estrutura, bg="white").pack(pady=5)
RoundedButton(home_card.inner, "CARREGAR KMZ", analisar_kmz, 280, 55).pack(pady=30)

# PREÇOS (Atualizado dinamicamente para incluir o novo splitter conectorizado)
prices_card = RoundedFrame(view_prices, 720, 520); prices_card.place(relx=0.5, rely=0.5, anchor="center")
row, col = 0, 0
for item, valor in PRECOS_PADRAO.items():
    Label(prices_card.inner, text=item, bg="white", font=("Segoe UI", 8, "bold"), fg=GIGA_CINZA_TXT).grid(row=row, column=col, sticky="e", pady=2)
    e = Entry(prices_card.inner, width=10, justify="right"); e.insert(0, f"{valor:.2f}"); e.grid(row=row, column=col+1, padx=10, pady=2); entradas_preco[item] = e
    row += 1
    if row > 17: row, col = 0, 2  # Ajustado limite de linhas devido ao novo item

# LOG
log_card = RoundedFrame(view_log, 720, 520); log_card.place(relx=0.5, rely=0.5, anchor="center")
RoundedButton(log_card.inner, "SALVAR CSV", salvar, 200, 40, bg_color=GIGA_VERDE, fg_color=GIGA_AZUL).pack(anchor="ne", pady=10)
janela_debug = ScrolledText(log_card.inner, font=("Consolas", 9), bg="#FAFAFA", bd=0); janela_debug.pack(fill="both", expand=True)

lbl_status = Label(root, text="Pronto.", bg=GIGA_AZUL, fg="white", font=("Segoe UI", 9)); lbl_status.pack(side="bottom", fill="x")

nav_to_home(); root.mainloop()