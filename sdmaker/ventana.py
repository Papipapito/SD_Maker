"""ventana.py — la ventana de MSXsdmaker (tkinter). El trabajo pesado va en un hilo; los avisos llegan por una cola.
Los textos son claves de idioma.py (tx(clave)); al cambiar de idioma la ventana se reconstruye con lo elegido."""
import os
import queue
import sys
import threading
import tkinter as tk
import webbrowser
from tkinter import filedialog, messagebox, simpledialog, ttk

from . import (VERSION, actualizar, ayudante_macos, contenido, dispositivos, idioma, novedades, ocm, particiones,
               proceso, ventana_actualizar, ventana_nextor, ventana_ocm)
from .dispositivos import formato_tamano
from .idioma import t as tx

ESQUEMAS = [("fat16-2g", "v.esq.fat16-2g"), ("fat16-4g", "v.esq.fat16-4g"), ("fat32", "v.esq.fat32")]
AVISO_FAT32 = "v.aviso_fat32"
TITULO = "MSX SD Maker"


class Ventana:
    def __init__(self, raiz):
        self.raiz = raiz
        self.cola = queue.Queue()
        self.tarjetas = []
        self.trabajando = False
        self.maquina = tk.StringVar(value="fpga")
        self.esquema = tk.StringVar(value="fat16-2g")
        self.cantidad = tk.IntVar(value=1)
        self.resto = tk.BooleanVar(value=False)
        self.sistema = tk.StringVar(value="nextor214")
        self.etiqueta = tk.StringVar(value="MSX")
        self.grupos = {g[0]: tk.BooleanVar(value=True) for g in contenido.GRUPOS + contenido.GRUPOS_OCM}
        d = contenido.OPCIONES_N3
        self.n3 = {k: tk.BooleanVar(value=d[k]) for k in ("yenslash", "bufinsert", "btm")}
        self.dirk = tk.StringVar(value=d["dirk"])
        self.nombre_idioma = tk.StringVar(value=dict(idioma.IDIOMAS)[idioma.actual()])
        self.pack = None                    # el OCM-SDBIOS Pack de KdL (ocm.Pack), si se encuentra
        self._pack_estado = ("buscando", None)      # buscando, leyendo (nombre), listo o error (texto)
        self._estado = ("v.listo", None) if sys.platform == "darwin" else (None, "")     # (clave, texto)
        self._maquina_grupos = None
        self.bios = ocm.por_defecto()       # [(nombre, receta)] de las BIOS del OCM
        self._construir()
        self._pintar_estado()
        self._pintar_pack()
        self._maquina_elegida()
        self.actualizar_tarjetas()
        self.raiz.after(100, self._leer_cola)
        threading.Thread(target=self._novedades, daemon=True).start()   # sin red no pasa nada
        threading.Thread(target=self._buscar_pack, daemon=True).start()

    # ------------------------------------------------------------------ el idioma
    def cambiar_idioma(self, nombre):
        codigo = {n: c for c, n in idioma.IDIOMAS}.get(nombre)
        if codigo is None or codigo == idioma.actual():
            return
        idioma.fijar(codigo, recordar=True)
        self.raiz.after_idle(self._reconstruir)

    def _reconstruir(self):
        """Vuelve a hacer la ventana en el idioma nuevo sin perder lo elegido (todo vive en las variables de tk, en
        self.bios y en self.pack) ni el registro, el avance o la tarjeta elegida."""
        indice = self.combo.current()
        registro = self.log.get("1.0", "end-1c")
        avance = self.barra["value"]
        for w in self.raiz.winfo_children():
            w.destroy()
        self._construir()
        self.log.insert("end", registro)
        self.log.see("end")
        self.barra["value"] = avance
        self._pintar_estado()
        self._maquina_elegida(conservar=True)
        self._pintar_pack()
        self._pintar_tarjetas(indice)
        self._bloquear(self.trabajando)

    def _poner_estado(self, clave=None, texto=None):
        self._estado = (clave, texto)
        self._pintar_estado()

    def _pintar_estado(self):
        clave, texto = self._estado
        self.estado["text"] = tx(clave) if clave else texto

    def _puntos(self, clave):
        """Un texto que acaba en … (en la interfaz clásica, con tres puntos)."""
        texto = tx(clave)
        return texto if sys.platform == "darwin" else texto.replace("…", "...")

    def _selector_idioma(self, padre):
        c = ttk.Combobox(padre, state="readonly", width=9, textvariable=self.nombre_idioma,
                         values=[n for _, n in idioma.IDIOMAS])
        c.bind("<<ComboboxSelected>>", lambda e: self.cambiar_idioma(self.nombre_idioma.get()))
        return c

    # ------------------------------------------------------------------ el pack de KdL (MSXBOOK y demas OCM)
    def _buscar_pack(self, ruta=None):
        ruta = ruta or ocm.buscar()
        if not ruta:
            self.cola.put(("pack", None, None))
            return
        try:
            pack = ocm.abrir(ruta)
            problemas = pack.problemas()
            self.cola.put(("pack", pack if not problemas else None,
                           None if not problemas else "%s: %s" % (os.path.basename(ruta), "; ".join(problemas[:3]))))
        except Exception as e:
            self.cola.put(("pack", None, "%s: %s" % (os.path.basename(ruta), e)))

    def _pack_listo(self, pack, error):
        self.pack = pack
        self._pack_estado = ("listo", None) if pack else ("error", error)
        self._pintar_pack()
        if not pack and self.maquina.get() == "ocm":
            self.maquina.set("fpga")
        self._maquina_elegida()

    def _pintar_pack(self):
        estado, dato = self._pack_estado
        if estado == "leyendo":
            self.pack_txt["text"] = tx("v.leyendo", dato)
        elif estado == "buscando":
            self.pack_txt["text"] = tx("v.buscando_pack")
        elif estado == "listo":
            self.pack_txt["text"] = tx("v.pack_en", self.pack.texto(), self.pack.ruta)
            self.pack_txt["foreground"] = "#006000"
        else:
            self.pack_txt["text"] = (tx("v.pack_no_vale", dato) if dato else "") + tx(
                "v.pack_falta", os.path.join(ocm.carpeta_programa(), ocm.CARPETA))
            self.pack_txt["foreground"] = "#b00000"
        self.r_ocm.state(["!disabled"] if self.pack else ["disabled"])

    def buscar_pack(self):
        ruta = filedialog.askopenfilename(title=tx("v.buscar_pack_titulo"),
                                          filetypes=[("OCM-SDBIOS Pack", "*.7z *.zip"), (tx("g.todos"), "*.*")])
        if ruta:
            self._pack_estado = ("leyendo", os.path.basename(ruta))
            self._pintar_pack()
            threading.Thread(target=self._buscar_pack, args=(ruta,), daemon=True).start()

    def opciones_bios(self):
        if not self.pack:
            return
        nueva = ventana_ocm.elegir(self.raiz, self.pack, self.bios)
        if nueva:
            self.bios = nueva
            self._maquina_elegida()

    def crear_bios_nextor(self):
        ventana_nextor.abrir(self.raiz)

    def _maquina_elegida(self, conservar=False):
        """conservar: la ventana se ha rehecho (otro idioma): se vuelven a poner las casillas, con lo que estaba marcado."""
        ocm_ = self.maquina.get() == "ocm"
        if ocm_:
            self.f3_fpga.pack_forget()
            self.f3_ocm.pack(fill="x", padx=6, pady=(4, 2), before=self.fo)
            self.r_fat32.state(["disabled"])
            if self.esquema.get() == "fat32":
                self.esquema.set("fat16-2g")
            textos = ["%-13s %s" % (n, ocm.describir(r, self.pack) if self.pack else ocm.nombre_tipo(r["tipo"]))
                      for n, r in self.bios]
            self.bios_txt["text"] = "\n".join(textos)
        else:
            self.f3_ocm.pack_forget()
            self.f3_fpga.pack(fill="x", before=self.fo)
            self.r_fat32.state(["!disabled"])
        # los programas de cada maquina, con sus valores por defecto al cambiar
        if conservar or self._maquina_grupos != self.maquina.get():
            cambiada = self._maquina_grupos != self.maquina.get()
            self._maquina_grupos = self.maquina.get()
            for w in self.rej.winfo_children():
                w.destroy()
            defecto = contenido.grupos_por_defecto(self.maquina.get())
            for i, (clave, texto, _, _, _) in enumerate(contenido.grupos_de(self.maquina.get())):
                if cambiada:
                    self.grupos[clave].set(clave in defecto)
                texto = tx(texto)
                if sys.platform == "darwin" and idioma.existe("v.grupo_mac." + clave):
                    texto = tx("v.grupo_mac." + clave)
                opciones = {"style": "Card.TCheckbutton"} if sys.platform == "darwin" else {}
                ttk.Checkbutton(self.rej, text=texto, variable=self.grupos[clave], **opciones).grid(
                    row=i // 2, column=i % 2, sticky="w", padx=(0, 20), pady=1)
        self._recalcular()

    def _sistema(self):
        return ocm.sistema_de(self.bios) if self.maquina.get() == "ocm" else self.sistema.get()

    # ------------------------------------------------------------------ version nueva en GitHub
    def _novedades(self):
        n = novedades.hay_nueva()
        if n:
            self.raiz.after(0, self._avisar_novedad, *n)

    def _avisar_novedad(self, version, url):
        self.escribir_log(tx("v.novedad_log", version, VERSION, url))
        if messagebox.askyesno(TITULO, tx("v.novedad_pregunta", version, VERSION)):
            webbrowser.open(url)

    # ------------------------------------------------------------------ interfaz
    def _construir(self):
        if sys.platform == "darwin":
            self._construir_macos()
            return
        self._construir_clasica()

    def _construir_macos(self):
        """La misma interfaz funcional, dispuesta como una aplicación moderna de macOS."""
        self.raiz.title(TITULO)
        self.raiz.minsize(1000, 780)
        self.raiz.geometry("1120x940")
        # Los colores NSColor cambian solos cuando macOS alterna entre apariencia clara y oscura.
        fondo, tarjeta, borde = "systemWindowBackgroundColor", "systemControlBackgroundColor", "systemSeparatorColor"
        primer_plano, secundario, peligro = "systemTextColor", "systemSecondaryLabelColor", "systemRedColor"
        self.raiz.configure(background=fondo)
        estilo = ttk.Style()
        estilo.configure("App.TFrame", background=fondo)
        estilo.configure("Card.TFrame", background=tarjeta)
        estilo.configure("Card.TLabel", background=tarjeta, foreground=primer_plano)
        estilo.configure("Secondary.Card.TLabel", background=tarjeta, foreground=secundario)
        estilo.configure("Danger.Card.TLabel", background=tarjeta, foreground=peligro)
        estilo.configure("Card.TCheckbutton", background=tarjeta)
        estilo.configure("Card.TRadiobutton", background=tarjeta)
        estilo.configure("Primary.TButton", font=("Helvetica Neue", 13, "bold"))

        def card(padre, titulo, subtitulo=None, expand=False):
            exterior = tk.Frame(padre, background=tarjeta, highlightbackground=borde, highlightthickness=1,
                                bd=0, padx=16, pady=13)
            exterior.pack(fill="both" if expand else "x", expand=expand, pady=(0, 12))
            cab = tk.Frame(exterior, background=tarjeta)
            cab.pack(fill="x", pady=(0, 9))
            tk.Label(cab, text=titulo, background=tarjeta, foreground=primer_plano,
                     font=("Helvetica Neue", 15, "bold")).pack(side="left")
            if subtitulo:
                tk.Label(cab, text=subtitulo, background=tarjeta, foreground=secundario,
                         font=("Helvetica Neue", 11)).pack(side="right", pady=(3, 0))
            cuerpo = ttk.Frame(exterior, style="Card.TFrame")
            cuerpo.pack(fill="both", expand=True)
            return cuerpo

        cabecera = tk.Frame(self.raiz, background=fondo)
        cabecera.pack(fill="x", padx=22, pady=(18, 12))
        titulos = tk.Frame(cabecera, background=fondo)
        titulos.pack(side="left")
        tk.Label(titulos, text=TITULO, background=fondo, foreground=primer_plano,
                 font=("Helvetica Neue", 24, "bold")).pack(anchor="w")
        tk.Label(titulos, text=tx("v.lema"), background=fondo, foreground=secundario,
                 font=("Helvetica Neue", 13)).pack(anchor="w", pady=(2, 0))
        derecha_cab = tk.Frame(cabecera, background=fondo)
        derecha_cab.pack(side="right", anchor="n", pady=4)
        tk.Label(derecha_cab, text=tx("v.version", VERSION), background=fondo, foreground=secundario,
                 font=("Helvetica Neue", 11), padx=4, pady=2).pack(anchor="e")
        fila = tk.Frame(derecha_cab, background=fondo)
        fila.pack(anchor="e", pady=(4, 0))
        tk.Label(fila, text=tx("v.idioma"), background=fondo, foreground=secundario,
                 font=("Helvetica Neue", 11)).pack(side="left", padx=(0, 6))
        self._selector_idioma(fila).pack(side="left")

        contenido_raiz = ttk.Frame(self.raiz, style="App.TFrame")
        contenido_raiz.pack(fill="both", expand=True, padx=22)

        f0 = card(contenido_raiz, tx("v.maquina"), tx("v.maquina_sub.mac"))
        fila = ttk.Frame(f0, style="Card.TFrame")
        fila.pack(fill="x")
        ttk.Radiobutton(fila, text=tx(contenido.MAQUINAS["fpga"]), value="fpga", variable=self.maquina,
                        command=self._maquina_elegida, style="Card.TRadiobutton").pack(side="left", padx=(0, 20))
        self.r_ocm = ttk.Radiobutton(fila, text=tx("v.r_ocm"), value="ocm",
                                     variable=self.maquina, command=self._maquina_elegida,
                                     style="Card.TRadiobutton")
        self.r_ocm.pack(side="left")
        self.r_ocm.state(["disabled"])
        fila = ttk.Frame(f0, style="Card.TFrame")
        fila.pack(fill="x", pady=(8, 0))
        self.pack_txt = ttk.Label(fila, text="", justify="left",
                                  style="Secondary.Card.TLabel", wraplength=850)
        self.pack_txt.pack(side="left", fill="x", expand=True)
        ttk.Button(fila, text=self._puntos("v.buscar_pack"), command=self.buscar_pack).pack(side="right", padx=(12, 0))

        columnas = ttk.Frame(contenido_raiz, style="App.TFrame")
        columnas.pack(fill="both", expand=True)
        columnas.columnconfigure(0, weight=1, uniform="columna")
        columnas.columnconfigure(1, weight=1, uniform="columna")
        columnas.rowconfigure(0, weight=1)
        izquierda = ttk.Frame(columnas, style="App.TFrame")
        derecha = ttk.Frame(columnas, style="App.TFrame")
        izquierda.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        derecha.grid(row=0, column=1, sticky="nsew", padx=(6, 0))

        f1 = card(izquierda, tx("v.f1.mac"), tx("v.f1_sub.mac"))
        fila = ttk.Frame(f1, style="Card.TFrame")
        fila.pack(fill="x")
        self.combo = ttk.Combobox(fila, state="readonly")
        self.combo.pack(side="left", fill="x", expand=True)
        self.combo.bind("<<ComboboxSelected>>", lambda e: self._tarjeta_elegida())
        ttk.Button(fila, text=tx("v.actualizar"), command=self.actualizar_tarjetas).pack(side="left", padx=(10, 0))
        self.info = ttk.Label(f1, text="", justify="left", style="Secondary.Card.TLabel", wraplength=500)
        self.info.pack(fill="x", pady=(8, 0))

        f2 = card(izquierda, tx("v.f2.mac"), tx("v.f2_sub.mac"), expand=True)
        fila = ttk.Frame(f2, style="Card.TFrame")
        fila.pack(fill="x")
        for clave, texto in ESQUEMAS:
            rb = ttk.Radiobutton(fila, text=tx(texto), value=clave, variable=self.esquema, command=self._recalcular,
                                 style="Card.TRadiobutton")
            rb.pack(side="left", padx=(0, 14))
            if clave == "fat32":
                self.r_fat32 = rb
        fila = ttk.Frame(f2, style="Card.TFrame")
        fila.pack(fill="x", pady=(10, 0))
        ttk.Label(fila, text=tx("v.cantidad.mac"), style="Card.TLabel").pack(side="left")
        self.spin = ttk.Spinbox(fila, from_=1, to=8, width=4, textvariable=self.cantidad, command=self._recalcular)
        self.spin.pack(side="left", padx=8)
        self.spin.bind("<KeyRelease>", lambda e: self._recalcular())
        self.max_txt = ttk.Label(fila, text="", style="Secondary.Card.TLabel", wraplength=340)
        self.max_txt.pack(side="left", fill="x", expand=True)
        self.chk_resto = ttk.Checkbutton(f2, text=tx("v.resto.mac"),
                                         variable=self.resto, command=self._recalcular,
                                         style="Card.TCheckbutton")
        self.chk_resto.pack(anchor="w", pady=(8, 0))
        self.plan_txt = ttk.Label(f2, text="", justify="left", font=("Menlo", 10), style="Card.TLabel")
        self.plan_txt.pack(fill="x", pady=(10, 2))
        self.aviso = ttk.Label(f2, text="", justify="left", style="Danger.Card.TLabel", wraplength=500)
        self.aviso.pack(fill="x")

        f3 = card(derecha, tx("v.f3.mac"), tx("v.sub_arranque.mac"))
        self.f3_fpga = ttk.Frame(f3, style="Card.TFrame")
        for clave, (texto, _, _) in contenido.SISTEMAS.items():
            texto = tx("v.sistema_mac." + clave) if idioma.existe("v.sistema_mac." + clave) else tx(texto)
            ttk.Radiobutton(self.f3_fpga, text=texto, value=clave, variable=self.sistema,
                            command=self._recalcular, style="Card.TRadiobutton").pack(anchor="w", pady=1)
        self.f3_ocm = ttk.Frame(f3, style="Card.TFrame")
        fila = ttk.Frame(self.f3_ocm, style="Card.TFrame")
        fila.pack(fill="x")
        ttk.Label(fila, text=tx("v.bios_creadas.mac"), style="Card.TLabel").pack(side="left")
        ttk.Button(fila, text=self._puntos("v.opciones_bios"), command=self.opciones_bios).pack(side="right")
        self.bios_txt = ttk.Label(self.f3_ocm, text="", justify="left", font=("Menlo", 10), style="Card.TLabel")
        self.bios_txt.pack(anchor="w", pady=(6, 0))
        fo = tk.Frame(f3, background=tarjeta, highlightbackground=borde, highlightthickness=1,
                      bd=0, padx=10, pady=8)
        fo.pack(fill="x", pady=(10, 0))
        self.fo = fo
        tk.Label(fo, text=tx("v.n3"), background=tarjeta, foreground=primer_plano,
                 font=("Helvetica Neue", 11, "bold")).pack(anchor="w", pady=(0, 3))
        self.controles_n3 = [
            ttk.Checkbutton(fo, text=tx("v.n3_yenslash.mac"), variable=self.n3["yenslash"]),
            ttk.Checkbutton(fo, text=tx("v.n3_bufinsert.mac"), variable=self.n3["bufinsert"]),
            ttk.Checkbutton(fo, text=tx("v.n3_btm.mac"), variable=self.n3["btm"]),
        ]
        for c in self.controles_n3:
            c.pack(anchor="w")
        fila = ttk.Frame(fo)
        fila.pack(anchor="w", pady=(3, 0))
        self.controles_n3.append(ttk.Label(fila, text=tx("v.n3_dir")))
        self.controles_n3.append(ttk.Radiobutton(fila, text=tx("v.n3_dir_k.mac"), value="", variable=self.dirk))
        self.controles_n3.append(ttk.Radiobutton(fila, text=tx("v.n3_dir_bytes.mac"), value="0", variable=self.dirk))
        for c in self.controles_n3[-3:]:
            c.pack(side="left", padx=(0, 9))
        ttk.Button(fo, text=self._puntos("v.crear_pack"), command=self.crear_bios_nextor).pack(
            anchor="e", pady=(7, 0))

        f4 = card(derecha, tx("v.f4.mac"), tx("v.sub_arranque.mac"), expand=True)
        self.rej = ttk.Frame(f4, style="Card.TFrame")
        self.rej.pack(fill="x")
        fila = ttk.Frame(f4, style="Card.TFrame")
        fila.pack(fill="x", pady=(10, 0))
        ttk.Button(fila, text=tx("v.todos"), command=lambda: self._todos(True)).pack(side="left")
        ttk.Button(fila, text=tx("v.ninguno"), command=lambda: self._todos(False)).pack(side="left", padx=6)
        ttk.Label(fila, text=tx("v.nombre.mac"), style="Secondary.Card.TLabel").pack(side="left", padx=(18, 6))
        ttk.Entry(fila, textvariable=self.etiqueta, width=13).pack(side="left")

        pie = tk.Frame(self.raiz, background=tarjeta, highlightbackground=borde, highlightthickness=1, bd=0,
                       padx=18, pady=12)
        pie.pack(fill="x", padx=22, pady=(0, 18))
        acciones = ttk.Frame(pie, style="Card.TFrame")
        acciones.pack(fill="x")
        ttk.Button(acciones, text=tx("v.salir"), command=self.raiz.destroy).pack(side="left")
        self.b_crear = ttk.Button(acciones, text=tx("v.preparar"), command=self.preparar, style="Primary.TButton")
        self.b_crear.pack(side="right")
        self.b_act = ttk.Button(acciones, text=self._puntos("v.act_tarjeta"), command=self.actualizar_tarjeta)
        self.b_act.pack(side="right", padx=(0, 10))
        self.b_imagen = ttk.Button(acciones, text=self._puntos("v.guardar_imagen"), command=self.guardar_imagen)
        self.b_imagen.pack(side="right", padx=(0, 10))
        self.estado = ttk.Label(pie, text="", style="Secondary.Card.TLabel")
        self.estado.pack(fill="x", pady=(10, 3))
        self.barra = ttk.Progressbar(pie, maximum=1000)
        self.barra.pack(fill="x")
        self.log = tk.Text(pie, height=4, font=("Menlo", 10), background="systemTextBackgroundColor",
                           foreground=primer_plano, insertbackground=primer_plano, relief="flat", highlightbackground=borde,
                           highlightthickness=1, padx=8, pady=6)
        self.log.pack(fill="x", pady=(8, 0))

    def _construir_clasica(self):
        self.raiz.title(tx("v.titulo.cl", VERSION))
        self.raiz.minsize(760, 680)
        p = {"padx": 8, "pady": 4}
        fila = ttk.Frame(self.raiz)
        fila.pack(fill="x", padx=8, pady=(4, 0))
        self._selector_idioma(fila).pack(side="right")
        ttk.Label(fila, text=tx("v.idioma")).pack(side="right", padx=(0, 6))
        f0 = ttk.LabelFrame(self.raiz, text=tx("v.maquina"))
        f0.pack(fill="x", **p)
        fila = ttk.Frame(f0)
        fila.pack(fill="x", padx=6, pady=(4, 0))
        ttk.Radiobutton(fila, text=tx(contenido.MAQUINAS["fpga"]), value="fpga", variable=self.maquina,
                        command=self._maquina_elegida).pack(side="left", padx=(0, 16))
        self.r_ocm = ttk.Radiobutton(fila, text=tx("v.r_ocm"), value="ocm",
                                     variable=self.maquina, command=self._maquina_elegida)
        self.r_ocm.pack(side="left")
        self.r_ocm.state(["disabled"])
        fila = ttk.Frame(f0)
        fila.pack(fill="x", padx=6, pady=(2, 6))
        self.pack_txt = ttk.Label(fila, text="", justify="left")
        self.pack_txt.pack(side="left", fill="x", expand=True)
        ttk.Button(fila, text=self._puntos("v.buscar_pack"), command=self.buscar_pack).pack(side="right")

        f1 = ttk.LabelFrame(self.raiz, text=tx("v.f1.cl"))
        f1.pack(fill="x", **p)
        fila = ttk.Frame(f1)
        fila.pack(fill="x", padx=6, pady=4)
        self.combo = ttk.Combobox(fila, state="readonly", width=78)
        self.combo.pack(side="left", fill="x", expand=True)
        self.combo.bind("<<ComboboxSelected>>", lambda e: self._tarjeta_elegida())
        ttk.Button(fila, text=tx("v.actualizar"), command=self.actualizar_tarjetas).pack(side="left", padx=6)
        self.info = ttk.Label(f1, text="", justify="left")
        self.info.pack(fill="x", padx=6, pady=(0, 6))

        f2 = ttk.LabelFrame(self.raiz, text=tx("v.f2.cl"))
        f2.pack(fill="x", **p)
        fila = ttk.Frame(f2)
        fila.pack(fill="x", padx=6, pady=4)
        for clave, texto in ESQUEMAS:
            rb = ttk.Radiobutton(fila, text=tx(texto), value=clave, variable=self.esquema, command=self._recalcular)
            rb.pack(side="left", padx=(0, 16))
            if clave == "fat32":
                self.r_fat32 = rb
        fila = ttk.Frame(f2)
        fila.pack(fill="x", padx=6)
        ttk.Label(fila, text=tx("v.cantidad.cl")).pack(side="left")
        self.spin = ttk.Spinbox(fila, from_=1, to=8, width=4, textvariable=self.cantidad, command=self._recalcular)
        self.spin.pack(side="left", padx=6)
        self.spin.bind("<KeyRelease>", lambda e: self._recalcular())
        self.max_txt = ttk.Label(fila, text="")
        self.max_txt.pack(side="left", padx=6)
        self.chk_resto = ttk.Checkbutton(f2, text=tx("v.resto.cl"),
                                         variable=self.resto, command=self._recalcular)
        self.chk_resto.pack(anchor="w", padx=6, pady=2)
        self.plan_txt = ttk.Label(f2, text="", justify="left", font=("Consolas", 9))
        self.plan_txt.pack(fill="x", padx=6, pady=(2, 2))
        self.aviso = ttk.Label(f2, text="", foreground="#b00000", justify="left")
        self.aviso.pack(fill="x", padx=6, pady=(0, 6))

        f3 = ttk.LabelFrame(self.raiz, text=tx("v.f3.cl"))
        f3.pack(fill="x", **p)
        self.f3_fpga = ttk.Frame(f3)
        for clave, (texto, _, _) in contenido.SISTEMAS.items():
            ttk.Radiobutton(self.f3_fpga, text=tx(texto), value=clave, variable=self.sistema,
                            command=self._recalcular).pack(anchor="w", padx=6)
        self.f3_ocm = ttk.Frame(f3)
        fila = ttk.Frame(self.f3_ocm)
        fila.pack(fill="x")
        ttk.Label(fila, text=tx("v.bios_creadas.cl")).pack(side="left")
        ttk.Button(fila, text=self._puntos("v.opciones_bios"), command=self.opciones_bios).pack(side="right")
        self.bios_txt = ttk.Label(self.f3_ocm, text="", justify="left", font=("Consolas", 9))
        self.bios_txt.pack(anchor="w", pady=(2, 0))
        fo = ttk.LabelFrame(f3, text=tx("v.n3"))
        fo.pack(fill="x", padx=6, pady=(2, 6))
        self.fo = fo
        self.controles_n3 = [
            ttk.Checkbutton(fo, text=tx("v.n3_yenslash.cl"), variable=self.n3["yenslash"]),
            ttk.Checkbutton(fo, text=tx("v.n3_bufinsert.cl"), variable=self.n3["bufinsert"]),
            ttk.Checkbutton(fo, text=tx("v.n3_btm.cl"), variable=self.n3["btm"]),
        ]
        for c in self.controles_n3:
            c.pack(anchor="w", padx=6)
        fila = ttk.Frame(fo)
        fila.pack(anchor="w", padx=6, pady=(0, 4))
        self.controles_n3.append(ttk.Label(fila, text=tx("v.n3_dir")))
        self.controles_n3.append(ttk.Radiobutton(fila, text=tx("v.n3_dir_k.cl"), value="", variable=self.dirk))
        self.controles_n3.append(ttk.Radiobutton(fila, text=tx("v.n3_dir_bytes.cl"), value="0", variable=self.dirk))
        for c in self.controles_n3[-3:]:
            c.pack(side="left", padx=(0, 10))
        ttk.Button(fo, text=self._puntos("v.crear_pack"), command=self.crear_bios_nextor).pack(
            anchor="e", padx=6, pady=(0, 4))

        f4 = ttk.LabelFrame(self.raiz, text=tx("v.f4.cl"))
        f4.pack(fill="x", **p)
        self.rej = ttk.Frame(f4)          # las casillas las pone _maquina_elegida (cambian con la maquina)
        self.rej.pack(fill="x", padx=6, pady=4)
        fila = ttk.Frame(f4)
        fila.pack(fill="x", padx=6, pady=(0, 6))
        ttk.Button(fila, text=tx("v.todos"), command=lambda: self._todos(True)).pack(side="left")
        ttk.Button(fila, text=tx("v.ninguno"), command=lambda: self._todos(False)).pack(side="left", padx=6)
        ttk.Label(fila, text=tx("v.nombre.cl")).pack(side="left", padx=(24, 4))
        ttk.Entry(fila, textvariable=self.etiqueta, width=14).pack(side="left")

        fila = ttk.Frame(self.raiz)
        fila.pack(fill="x", **p)
        self.b_crear = ttk.Button(fila, text=tx("v.preparar"), command=self.preparar)
        self.b_crear.pack(side="left")
        self.b_act = ttk.Button(fila, text=self._puntos("v.act_tarjeta"), command=self.actualizar_tarjeta)
        self.b_act.pack(side="left", padx=6)
        self.b_imagen = ttk.Button(fila, text=self._puntos("v.guardar_imagen"), command=self.guardar_imagen)
        self.b_imagen.pack(side="left")
        ttk.Button(fila, text=tx("v.salir"), command=self.raiz.destroy).pack(side="right")
        self.barra = ttk.Progressbar(self.raiz, maximum=1000)
        self.barra.pack(fill="x", **p)
        self.estado = ttk.Label(self.raiz, text="")
        self.estado.pack(fill="x", padx=8)
        self.log = tk.Text(self.raiz, height=8, font=("Consolas", 9))
        self.log.pack(fill="both", expand=True, **p)

    def _todos(self, valor):
        for v in self.grupos.values():
            v.set(valor)

    def escribir_log(self, texto):
        self.log.insert("end", texto + "\n")
        self.log.see("end")

    # ------------------------------------------------------------------ tarjetas
    def _unidades(self, t):
        sep = ", " if sys.platform == "darwin" else " "
        return sep.join(t["letras"]) or tx("v.sin_volumen" if sys.platform == "darwin" else "v.sin_unidad")

    def _disco(self, t):
        return tx("v.disco" + (".mac" if sys.platform == "darwin" else ".cl"), t["numero"])

    def actualizar_tarjetas(self):
        try:
            self.tarjetas = dispositivos.listar_tarjetas()
        except Exception as e:
            self.tarjetas = []
            self.escribir_log(tx("v.err_listar", e))
        self._pintar_tarjetas(0)

    def _pintar_tarjetas(self, indice=0):
        textos = ["%s   %s   %s   (%s, %s)" % (self._unidades(t), t["modelo"], formato_tamano(t["bytes"]),
                                                t["bus"], self._disco(t)) for t in self.tarjetas]
        self.combo["values"] = textos
        if textos:
            self.combo.current(min(max(indice, 0), len(textos) - 1))
        else:
            self.combo.set(tx("v.sin_tarjetas"))
        self._tarjeta_elegida()

    def tarjeta(self):
        i = self.combo.current()
        return self.tarjetas[i] if 0 <= i < len(self.tarjetas) else None

    def _tarjeta_elegida(self):
        t = self.tarjeta()
        if t is None:
            self.info["text"] = ""
        else:
            self.info["text"] = tx("v.info", formato_tamano(t["bytes"]), idioma.miles(t["sectores"]), self._actual(t))
        self._recalcular()

    def _actual(self, t):
        if sys.platform == "darwin":
            partes = t.get("particiones", [])
            if not partes:
                return tx("v.actual_sin_tabla")
            return ", ".join(tx("v.actual_particion", p["tipo"], formato_tamano(p["bytes"])) for p in partes)
        if sys.platform != "win32" or not dispositivos.es_admin():
            return tx("v.actual_admin")
        try:
            d = dispositivos.DiscoLectura(t["numero"])
            try:
                tabla = particiones.leer_tabla(lambda lba: d.leer(lba))
            finally:
                d.cerrar()
        except Exception as e:
            return tx("v.actual_no_se_puede", e)
        if not tabla:
            return tx("v.actual_sin_tabla")
        return ", ".join(tx("v.actual_particion", particiones.NOMBRES_TIPO.get(tipo, tx("v.actual_tipo", tipo)),
                            formato_tamano(n * 512)) for _, tipo, _, n in tabla)

    # ------------------------------------------------------------------ plan
    def _sectores(self):
        t = self.tarjeta()
        return t["sectores"] if t else None

    def plan(self, sectores=None):
        sectores = sectores or self._sectores()
        if not sectores:
            return None
        esquema = self.esquema.get()
        try:
            n = int(self.cantidad.get())
        except (tk.TclError, ValueError):
            n = 1
        return particiones.planificar(sectores, esquema, n, self.resto.get())

    def _recalcular(self):
        for c in getattr(self, "controles_n3", []):
            c.state(["!disabled"] if self._sistema().startswith("nextor3") else ["disabled"])
        sectores = self._sectores()
        esquema = self.esquema.get()
        fat16 = esquema != "fat32"
        self.spin.state(["!disabled"] if fat16 else ["disabled"])
        self.chk_resto.state(["!disabled"] if fat16 else ["disabled"])
        self.aviso["text"] = tx(AVISO_FAT32) if not fat16 else ""
        if not sectores:
            self.plan_txt["text"] = ""
            self.max_txt["text"] = ""
            return
        self.max_txt["text"] = ""
        if fat16:
            tam = particiones.GB2 if esquema == "fat16-2g" else particiones.GB4
            maximo = particiones.maximo_fat16(sectores, tam)
            self.spin.configure(to=max(1, maximo))
            self.max_txt["text"] = (tx("v.max", maximo, tx("v.max_ocm") if self.maquina.get() == "ocm"
                                       else tx("v.max_msximus"))
                                    if maximo else tx("v.max_pequena"))
            if maximo and int(self.cantidad.get() or 1) > maximo:
                self.cantidad.set(maximo)
        try:
            plan = self.plan()
        except ValueError as e:
            self.plan_txt["text"] = str(e)
            return
        lineas = []
        for p in plan:
            if p.numero == 1:
                uso = tx("v.plan_arranque") if self._sistema() != "ninguno" else ""
            else:
                uso = tx("v.plan_mapdrv", contenido.UNIDADES[p.numero - 2])
            lineas.append(tx("v.plan_linea", p.numero, "FAT32" if p.tipo == particiones.TIPO_FAT32 else "FAT16",
                             formato_tamano(p.bytes), uso))
        sobra = particiones.sin_usar(sectores, plan)
        if sobra > 2048:
            lineas.append(tx("v.plan_sin_usar", formato_tamano(sobra * 512)))
        self.plan_txt["text"] = "\n".join(lineas)

    # ------------------------------------------------------------------ acciones
    def _elegidos(self):
        validos = {g[0] for g in contenido.grupos_de(self.maquina.get())}
        return {k for k, v in self.grupos.items() if v.get() and k in validos}

    def _opciones(self):
        o = {k: v.get() for k, v in self.n3.items()}
        o["dirk"] = self.dirk.get()
        return o

    def _texto_opciones(self):
        if not self._sistema().startswith("nextor3"):
            return ""
        o = self._opciones()
        partes = [contenido.nombre_autoexec("nextor3", o)]
        partes += [t for k, t in (("yenslash", "YENSLASH ON"), ("bufinsert", "BUFINSERT"), ) if o[k]]
        partes.append(tx("v.dir_bytes") if o["dirk"] == "0" else tx("v.dir_k"))
        return tx("v.opciones") + ", ".join(partes)

    def _bloquear(self, si):
        self.trabajando = si
        for b in (self.b_crear, self.b_act, self.b_imagen):
            b.state(["disabled"] if si else ["!disabled"])

    def _listo_ocm(self):
        if self.maquina.get() != "ocm":
            return True
        if not self.pack:
            messagebox.showwarning(TITULO, tx("v.falta_pack"))
            return False
        return True

    def _texto_sistema(self):
        if self.maquina.get() != "ocm":
            return tx("v.sistema", tx(contenido.SISTEMAS[self.sistema.get()][0]))
        return tx("v.bios", self.pack.texto(), "\n".join("    %s  %s" % (n, ocm.describir(r, self.pack))
                                                         for n, r in self.bios))

    def preparar(self):
        if self.trabajando:
            return
        t = self.tarjeta()
        if t is None:
            messagebox.showwarning(TITULO, tx("v.conecta"))
            return
        if sys.platform == "win32" and not dispositivos.es_admin():
            if messagebox.askyesno(TITULO, tx("v.admin_pregunta")):
                relanzar_como_admin()
            return
        try:
            plan = self.plan()
        except ValueError as e:
            messagebox.showerror(TITULO, str(e))
            return
        if not self._listo_ocm():
            return
        texto = tx("v.borrar_texto", t["modelo"], formato_tamano(t["bytes"]), self._unidades(t), self._disco(t),
                   self.plan_txt["text"], self._texto_sistema(), self._texto_opciones())
        if not messagebox.askyesno(tx("v.borrar_titulo"), texto, icon="warning", default="no"):
            return

        if sys.platform == "darwin":
            datos_ocm = {"pack": self.pack, "bios": self.bios} if self.maquina.get() == "ocm" else None
            datos = ayudante_macos.datos_trabajo(t, plan, self._sistema(), self._elegidos(),
                                                 self.etiqueta.get() or "MSX", self._opciones(), datos_ocm)
            self._lanzar_macos(datos, tx("v.la_tarjeta"))
            return

        def abrir():
            return dispositivos.Disco(t["numero"])
        self._lanzar(abrir, plan, tx("v.la_tarjeta"))

    def actualizar_tarjeta(self):
        """Pone al dia la tarjeta elegida SIN formatearla: por su unidad montada, con ficheros normales (no hace falta
        ser administrador ni escribir el disco en crudo). Si tiene varias unidades, la de arranque."""
        if self.trabajando:
            messagebox.showinfo(TITULO, tx("v.act_ocupado"))
            return
        t = self.tarjeta()
        if t is None:
            messagebox.showwarning(TITULO, tx("v.conecta"))
            return
        carpetas = dispositivos.carpetas_montadas(t)
        if not carpetas:
            messagebox.showinfo(TITULO, tx("v.act_sin_unidad"))
            return
        candidatas = actualizar.elegir_arranque(carpetas)
        con_sistema = [c for c, ok in candidatas if ok]
        if len(carpetas) == 1:
            ruta = carpetas[0]
        elif len(con_sistema) == 1:
            ruta = con_sistema[0]
        else:
            ruta = ventana_actualizar.elegir_unidad(self.raiz, carpetas, con_sistema)
        if ruta:
            ventana_actualizar.abrir(self.raiz, ruta, self.pack)

    def guardar_imagen(self):
        if self.trabajando or not self._listo_ocm():
            return
        # 1.1: el tamano se pregunta siempre (antes, con una tarjeta conectada, la imagen salia del tamano de la tarjeta).
        # 1800M cabe en cualquier tarjeta de 2 GB (las de "2 GB" tienen menos de 2 GiB); en una mayor sobra el resto.
        tam = simpledialog.askstring(TITULO, tx("v.imagen_tamano"), initialvalue="1800M")
        if not tam:
            return
        try:
            t = tam.strip().upper().rstrip("B")
            sectores = int(float(t[:-1]) * {"M": 1 << 20, "G": 1 << 30}[t[-1]]) // 512
        except (ValueError, KeyError, IndexError):
            messagebox.showerror(TITULO, tx("v.imagen_invalida", tam))
            return
        ruta = filedialog.asksaveasfilename(title=tx("v.imagen_guardar"), defaultextension=".img",
                                            filetypes=[(tx("v.imagen_tipo"), "*.img"), (tx("g.todos"), "*.*")])
        if not ruta:
            return
        try:
            plan = self.plan(sectores)
        except ValueError as e:
            messagebox.showerror(TITULO, str(e))
            return

        def abrir():
            return dispositivos.Imagen(ruta, sectores)
        self._lanzar(abrir, plan, os.path.basename(ruta))

    def _lanzar(self, abrir, plan, destino):
        self._bloquear(True)
        self.log.delete("1.0", "end")
        self.barra["value"] = 0
        sistema, grupos, etiqueta = self._sistema(), self._elegidos(), self.etiqueta.get() or "MSX"
        datos_ocm = {"pack": self.pack, "bios": self.bios} if self.maquina.get() == "ocm" else None
        opciones = self._opciones()

        def trabajo():
            dev = None
            try:
                dev = abrir()
                inf = proceso.crear(dev, plan, sistema, grupos, etiqueta,
                                    lambda texto, f=None: self.cola.put(("aviso", texto, f)), opciones=opciones,
                                    ocm=datos_ocm)
                self.cola.put(("fin", inf, destino))
            except Exception as e:
                self.cola.put(("error", "%s: %s" % (type(e).__name__, e), destino))
            finally:
                if dev is not None:
                    try:
                        dev.cerrar()
                    except Exception as e:
                        self.cola.put(("aviso", tx("v.al_cerrar", e), None))
        threading.Thread(target=trabajo, daemon=True).start()

    def _lanzar_macos(self, datos, destino):
        self._bloquear(True)
        self.log.delete("1.0", "end")
        self.barra["value"] = 0
        self._poner_estado(clave="v.esperando_admin")

        def trabajo():
            try:
                inf = ayudante_macos.lanzar(
                    datos, lambda texto, f=None: self.cola.put(("aviso", texto, f)))
                self.cola.put(("fin", inf, destino))
            except Exception as e:
                self.cola.put(("error", "%s: %s" % (type(e).__name__, e), destino))
        threading.Thread(target=trabajo, daemon=True).start()

    def _leer_cola(self):
        try:
            while True:
                m = self.cola.get_nowait()
                if m[0] == "pack":
                    self._pack_listo(m[1], m[2])
                elif m[0] == "aviso":
                    self._poner_estado(texto=m[1][:110])
                    if m[2] is not None:
                        self.barra["value"] = int(m[2] * 1000)
                    if not m[1].startswith(idioma.prefijos("p.copiando")):
                        self.escribir_log(m[1])
                elif m[0] == "fin":
                    self._terminado(m[1], m[2])
                elif m[0] == "error":
                    self._bloquear(False)
                    self.escribir_log("ERROR: " + m[1])
                    messagebox.showerror(TITULO, tx("v.error_preparar", m[2], m[1]))
        except queue.Empty:
            pass
        self.raiz.after(100, self._leer_cola)

    def _terminado(self, inf, destino):
        self._bloquear(False)
        for p in inf["particiones"]:
            self.escribir_log(tx("v.log_particion", p["numero"], p["etiqueta"], p["geometria"]))
        self.escribir_log(tx("v.log_ficheros", inf["ficheros"], formato_tamano(inf["bytes"]), inf["segundos"]))
        if inf["errores"]:
            for e in inf["errores"]:
                self.escribir_log("ERROR: " + e)
            messagebox.showerror(TITULO, tx("v.fin_errores", destino, "\n".join(inf["errores"][:5])))
        else:
            messagebox.showinfo(TITULO, tx("v.fin_ok", destino[:1].upper() + destino[1:], inf["ficheros"]))
        self.raiz.after(2500, self.actualizar_tarjetas)


def relanzar_como_admin():
    import ctypes
    if getattr(sys, "frozen", False):
        exe, params = sys.executable, ""
    else:
        exe, params = sys.executable, '"%s"' % os.path.abspath(sys.argv[0])
    ctypes.windll.shell32.ShellExecuteW(None, "runas", exe, params, None, 1)
    sys.exit(0)


def nitido():
    """Que Windows no amplie la ventana como un mapa de bits en pantallas con escalado (125 %, 150 %...)."""
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass


def main():
    nitido()
    raiz = tk.Tk()
    try:
        estilo = ttk.Style()
        estilo.theme_use("vista" if sys.platform == "win32" else "aqua" if sys.platform == "darwin" else "clam")
        raiz.configure(background=estilo.lookup("TFrame", "background"))
    except tk.TclError:
        pass
    Ventana(raiz)
    raiz.mainloop()
