"""ventana.py — la ventana de MSXsdmaker (tkinter). El trabajo pesado va en un hilo; los avisos llegan por una cola."""
import os
import queue
import sys
import threading
import tkinter as tk
import webbrowser
from tkinter import filedialog, messagebox, simpledialog, ttk

from . import VERSION, ayudante_macos, contenido, dispositivos, novedades, ocm, particiones, proceso, ventana_ocm
from .dispositivos import formato_tamano

ESQUEMAS = [("fat16-2g", "FAT16 de 2 GB"), ("fat16-4g", "FAT16 de 4 GB"), ("fat32", "Una FAT32 (toda la tarjeta)")]
AVISO_FAT32 = ("Nextor 2.1.4 y 3.0 no leen FAT32: el MSX no arrancará MSX-DOS desde esta tarjeta.\n"
               "Sirve para el menú del MSXimus (ROM y DSK) y para la MSX Pico.")


class Ventana:
    def __init__(self, raiz):
        self.raiz = raiz
        raiz.title("MSX SD Maker %s: tarjetas para MSXimus, MSXnano, MSX Pico y MSXBOOK" % VERSION)
        raiz.minsize(760, 680)
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
        self.pack = None                    # el OCM-SDBIOS Pack de KdL (ocm.Pack), si se encuentra
        self.bios = ocm.por_defecto()       # [(nombre, receta)] de las BIOS del OCM
        self._construir()
        self._maquina_elegida()
        self.actualizar_tarjetas()
        self.raiz.after(100, self._leer_cola)
        threading.Thread(target=self._novedades, daemon=True).start()   # sin red no pasa nada
        threading.Thread(target=self._buscar_pack, daemon=True).start()

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
        if pack:
            self.pack_txt["text"] = "%s\nen %s" % (pack.texto(), pack.ruta)
            self.pack_txt["foreground"] = "#006000"
            self.r_ocm.state(["!disabled"])
        else:
            self.pack_txt["text"] = (("No vale el pack: %s\n" % error) if error else "") + (
                "Para el MSXBOOK hace falta el OCM-SDBIOS Pack de KdL: déjalo tal cual (el .7z) en la carpeta\n"
                "%s, junto a este programa, o búscalo con el botón." % os.path.join(ocm.carpeta_programa(), ocm.CARPETA))
            self.pack_txt["foreground"] = "#b00000"
            self.r_ocm.state(["disabled"])
            if self.maquina.get() == "ocm":
                self.maquina.set("fpga")
        self._maquina_elegida()

    def buscar_pack(self):
        ruta = filedialog.askopenfilename(title="El OCM-SDBIOS Pack de KdL (el .7z o el .zip)",
                                          filetypes=[("OCM-SDBIOS Pack", "*.7z *.zip"), ("Todos", "*.*")])
        if ruta:
            self.pack_txt["text"] = "Leyendo %s..." % os.path.basename(ruta)
            threading.Thread(target=self._buscar_pack, args=(ruta,), daemon=True).start()

    def opciones_bios(self):
        if not self.pack:
            return
        nueva = ventana_ocm.elegir(self.raiz, self.pack, self.bios)
        if nueva:
            self.bios = nueva
            self._maquina_elegida()

    def _maquina_elegida(self):
        ocm_ = self.maquina.get() == "ocm"
        if ocm_:
            self.f3_fpga.pack_forget()
            self.f3_ocm.pack(fill="x", padx=6, pady=(4, 2), before=self.fo)
            self.r_fat32.state(["disabled"])
            if self.esquema.get() == "fat32":
                self.esquema.set("fat16-2g")
            textos = ["%-13s %s" % (n, ocm.describir(r, self.pack) if self.pack else ocm.NOMBRE_TIPO[r["tipo"]])
                      for n, r in self.bios]
            self.bios_txt["text"] = "\n".join(textos)
        else:
            self.f3_ocm.pack_forget()
            self.f3_fpga.pack(fill="x", before=self.fo)
            self.r_fat32.state(["!disabled"])
        # los programas de cada maquina, con sus valores por defecto al cambiar
        if getattr(self, "_maquina_grupos", None) != self.maquina.get():
            self._maquina_grupos = self.maquina.get()
            for w in self.rej.winfo_children():
                w.destroy()
            defecto = contenido.grupos_por_defecto(self.maquina.get())
            for i, (clave, texto, _, _, _) in enumerate(contenido.grupos_de(self.maquina.get())):
                self.grupos[clave].set(clave in defecto)
                if sys.platform == "darwin":
                    texto = {"sofarun": "SofaRun (ROM, DSK y cintas)", "mm": "Multi Mente (ficheros)",
                             "util": "Utilidades (UTIL)", "wifi": "Red WiFi / UNAPI", "fonts": "Fuentes de pantalla",
                             "musica": "Música (MoonBlaster, RoboPlay…)", "hub": "HUB (paquetes)",
                             "ia": "IA (cliente de chat)", "varios": "mapper e indev",
                             "fpga": "Herramientas FPGA (MXUPDATE)", "flash": "Flasheo del FPGA"}.get(clave, texto)
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
        self.escribir_log("Hay una versión nueva de MSX SD Maker, la %s (esta es la %s): %s" % (version, VERSION, url))
        if messagebox.askyesno("MSX SD Maker", "Hay una versión nueva de MSX SD Maker, la %s (esta es la %s).\n\n"
                               "¿Abrir la página de descarga?" % (version, VERSION)):
            webbrowser.open(url)

    # ------------------------------------------------------------------ interfaz
    def _construir(self):
        if sys.platform == "darwin":
            self._construir_macos()
            return
        self._construir_clasica()

    def _construir_macos(self):
        """La misma interfaz funcional, dispuesta como una aplicación moderna de macOS."""
        self.raiz.title("MSX SD Maker")
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
        tk.Label(titulos, text="MSX SD Maker", background=fondo, foreground=primer_plano,
                 font=("Helvetica Neue", 24, "bold")).pack(anchor="w")
        tk.Label(titulos, text="Prepara y verifica tarjetas para tu MSX", background=fondo, foreground=secundario,
                 font=("Helvetica Neue", 13)).pack(anchor="w", pady=(2, 0))
        tk.Label(cabecera, text="versión %s" % VERSION, background=fondo, foreground=secundario,
                 font=("Helvetica Neue", 11), padx=4, pady=5).pack(side="right", anchor="n", pady=4)

        contenido_raiz = ttk.Frame(self.raiz, style="App.TFrame")
        contenido_raiz.pack(fill="both", expand=True, padx=22)

        f0 = card(contenido_raiz, "Máquina", "Selecciona el hardware de destino")
        fila = ttk.Frame(f0, style="Card.TFrame")
        fila.pack(fill="x")
        ttk.Radiobutton(fila, text=contenido.MAQUINAS["fpga"], value="fpga", variable=self.maquina,
                        command=self._maquina_elegida, style="Card.TRadiobutton").pack(side="left", padx=(0, 20))
        self.r_ocm = ttk.Radiobutton(fila, text="MSXBOOK, OneChipBook o 1chipMSX (OCM-PLD)", value="ocm",
                                     variable=self.maquina, command=self._maquina_elegida,
                                     style="Card.TRadiobutton")
        self.r_ocm.pack(side="left")
        self.r_ocm.state(["disabled"])
        fila = ttk.Frame(f0, style="Card.TFrame")
        fila.pack(fill="x", pady=(8, 0))
        self.pack_txt = ttk.Label(fila, text="Buscando el OCM-SDBIOS Pack de KdL...", justify="left",
                                  style="Secondary.Card.TLabel", wraplength=850)
        self.pack_txt.pack(side="left", fill="x", expand=True)
        ttk.Button(fila, text="Buscar el pack…", command=self.buscar_pack).pack(side="right", padx=(12, 0))

        columnas = ttk.Frame(contenido_raiz, style="App.TFrame")
        columnas.pack(fill="both", expand=True)
        columnas.columnconfigure(0, weight=1, uniform="columna")
        columnas.columnconfigure(1, weight=1, uniform="columna")
        columnas.rowconfigure(0, weight=1)
        izquierda = ttk.Frame(columnas, style="App.TFrame")
        derecha = ttk.Frame(columnas, style="App.TFrame")
        izquierda.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        derecha.grid(row=0, column=1, sticky="nsew", padx=(6, 0))

        f1 = card(izquierda, "1  Tarjeta SD", "Medio externo y extraíble")
        fila = ttk.Frame(f1, style="Card.TFrame")
        fila.pack(fill="x")
        self.combo = ttk.Combobox(fila, state="readonly")
        self.combo.pack(side="left", fill="x", expand=True)
        self.combo.bind("<<ComboboxSelected>>", lambda e: self._tarjeta_elegida())
        ttk.Button(fila, text="Actualizar", command=self.actualizar_tarjetas).pack(side="left", padx=(10, 0))
        self.info = ttk.Label(f1, text="", justify="left", style="Secondary.Card.TLabel", wraplength=500)
        self.info.pack(fill="x", pady=(8, 0))

        f2 = card(izquierda, "2  Particiones", "Formato compatible con Nextor", expand=True)
        fila = ttk.Frame(f2, style="Card.TFrame")
        fila.pack(fill="x")
        for clave, texto in ESQUEMAS:
            rb = ttk.Radiobutton(fila, text=texto, value=clave, variable=self.esquema, command=self._recalcular,
                                 style="Card.TRadiobutton")
            rb.pack(side="left", padx=(0, 14))
            if clave == "fat32":
                self.r_fat32 = rb
        fila = ttk.Frame(f2, style="Card.TFrame")
        fila.pack(fill="x", pady=(10, 0))
        ttk.Label(fila, text="Cantidad", style="Card.TLabel").pack(side="left")
        self.spin = ttk.Spinbox(fila, from_=1, to=8, width=4, textvariable=self.cantidad, command=self._recalcular)
        self.spin.pack(side="left", padx=8)
        self.spin.bind("<KeyRelease>", lambda e: self._recalcular())
        self.max_txt = ttk.Label(fila, text="", style="Secondary.Card.TLabel", wraplength=340)
        self.max_txt.pack(side="left", fill="x", expand=True)
        self.chk_resto = ttk.Checkbutton(f2, text="Usar lo que sobre en una última partición FAT16 (hasta 4 GB)",
                                         variable=self.resto, command=self._recalcular,
                                         style="Card.TCheckbutton")
        self.chk_resto.pack(anchor="w", pady=(8, 0))
        self.plan_txt = ttk.Label(f2, text="", justify="left", font=("Menlo", 10), style="Card.TLabel")
        self.plan_txt.pack(fill="x", pady=(10, 2))
        self.aviso = ttk.Label(f2, text="", justify="left", style="Danger.Card.TLabel", wraplength=500)
        self.aviso.pack(fill="x")

        f3 = card(derecha, "3  Sistema", "Partición de arranque")
        self.f3_fpga = ttk.Frame(f3, style="Card.TFrame")
        for clave, (texto, _, _) in contenido.SISTEMAS.items():
            texto = {"msxdos": "MSX-DOS básico (MSX-DOS 2 + MSX-DOS 1)",
                     "ninguno": "Ninguno (sólo formatear)"}.get(clave, texto)
            ttk.Radiobutton(self.f3_fpga, text=texto, value=clave, variable=self.sistema,
                            command=self._recalcular, style="Card.TRadiobutton").pack(anchor="w", pady=1)
        self.f3_ocm = ttk.Frame(f3, style="Card.TFrame")
        fila = ttk.Frame(self.f3_ocm, style="Card.TFrame")
        fila.pack(fill="x")
        ttk.Label(fila, text="BIOS creadas con el pack de KdL", style="Card.TLabel").pack(side="left")
        ttk.Button(fila, text="Opciones de las BIOS…", command=self.opciones_bios).pack(side="right")
        self.bios_txt = ttk.Label(self.f3_ocm, text="", justify="left", font=("Menlo", 10), style="Card.TLabel")
        self.bios_txt.pack(anchor="w", pady=(6, 0))
        fo = tk.Frame(f3, background=tarjeta, highlightbackground=borde, highlightthickness=1,
                      bd=0, padx=10, pady=8)
        fo.pack(fill="x", pady=(10, 0))
        self.fo = fo
        tk.Label(fo, text="Opciones de Nextor 3", background=tarjeta, foreground=primer_plano,
                 font=("Helvetica Neue", 11, "bold")).pack(anchor="w", pady=(0, 3))
        self.controles_n3 = [
            ttk.Checkbutton(fo, text="Barra invertida en las rutas (YENSLASH ON)", variable=self.n3["yenslash"]),
            ttk.Checkbutton(fo, text="Modo inserción al escribir (BUFINSERT)", variable=self.n3["bufinsert"]),
            ttk.Checkbutton(fo, text="AUTOEXEC.BTM (admite GOTO, GOSUB y END)", variable=self.n3["btm"]),
        ]
        for c in self.controles_n3:
            c.pack(anchor="w")
        fila = ttk.Frame(fo)
        fila.pack(anchor="w", pady=(3, 0))
        self.controles_n3.append(ttk.Label(fila, text="Tamaños en DIR:"))
        self.controles_n3.append(ttk.Radiobutton(fila, text="en K", value="", variable=self.dirk))
        self.controles_n3.append(ttk.Radiobutton(fila, text="en bytes", value="0", variable=self.dirk))
        for c in self.controles_n3[-3:]:
            c.pack(side="left", padx=(0, 9))

        f4 = card(derecha, "4  Programas", "Partición de arranque", expand=True)
        self.rej = ttk.Frame(f4, style="Card.TFrame")
        self.rej.pack(fill="x")
        fila = ttk.Frame(f4, style="Card.TFrame")
        fila.pack(fill="x", pady=(10, 0))
        ttk.Button(fila, text="Todos", command=lambda: self._todos(True)).pack(side="left")
        ttk.Button(fila, text="Ninguno", command=lambda: self._todos(False)).pack(side="left", padx=6)
        ttk.Label(fila, text="Nombre", style="Secondary.Card.TLabel").pack(side="left", padx=(18, 6))
        ttk.Entry(fila, textvariable=self.etiqueta, width=13).pack(side="left")

        pie = tk.Frame(self.raiz, background=tarjeta, highlightbackground=borde, highlightthickness=1, bd=0,
                       padx=18, pady=12)
        pie.pack(fill="x", padx=22, pady=(0, 18))
        acciones = ttk.Frame(pie, style="Card.TFrame")
        acciones.pack(fill="x")
        ttk.Button(acciones, text="Salir", command=self.raiz.destroy).pack(side="left")
        self.b_crear = ttk.Button(acciones, text="Preparar la tarjeta", command=self.preparar, style="Primary.TButton")
        self.b_crear.pack(side="right")
        self.b_imagen = ttk.Button(acciones, text="Guardar como imagen…", command=self.guardar_imagen)
        self.b_imagen.pack(side="right", padx=(0, 10))
        self.estado = ttk.Label(pie, text="Listo", style="Secondary.Card.TLabel")
        self.estado.pack(fill="x", pady=(10, 3))
        self.barra = ttk.Progressbar(pie, maximum=1000)
        self.barra.pack(fill="x")
        self.log = tk.Text(pie, height=4, font=("Menlo", 10), background="systemTextBackgroundColor",
                           foreground=primer_plano, insertbackground=primer_plano, relief="flat", highlightbackground=borde,
                           highlightthickness=1, padx=8, pady=6)
        self.log.pack(fill="x", pady=(8, 0))

    def _construir_clasica(self):
        p = {"padx": 8, "pady": 4}
        f0 = ttk.LabelFrame(self.raiz, text="Máquina")
        f0.pack(fill="x", **p)
        fila = ttk.Frame(f0)
        fila.pack(fill="x", padx=6, pady=(4, 0))
        ttk.Radiobutton(fila, text=contenido.MAQUINAS["fpga"], value="fpga", variable=self.maquina,
                        command=self._maquina_elegida).pack(side="left", padx=(0, 16))
        self.r_ocm = ttk.Radiobutton(fila, text="MSXBOOK, OneChipBook o 1chipMSX (OCM-PLD)", value="ocm",
                                     variable=self.maquina, command=self._maquina_elegida)
        self.r_ocm.pack(side="left")
        self.r_ocm.state(["disabled"])
        fila = ttk.Frame(f0)
        fila.pack(fill="x", padx=6, pady=(2, 6))
        self.pack_txt = ttk.Label(fila, text="Buscando el OCM-SDBIOS Pack de KdL...", justify="left")
        self.pack_txt.pack(side="left", fill="x", expand=True)
        ttk.Button(fila, text="Buscar el pack...", command=self.buscar_pack).pack(side="right")

        f1 = ttk.LabelFrame(self.raiz, text="1. Tarjeta SD")
        f1.pack(fill="x", **p)
        fila = ttk.Frame(f1)
        fila.pack(fill="x", padx=6, pady=4)
        self.combo = ttk.Combobox(fila, state="readonly", width=78)
        self.combo.pack(side="left", fill="x", expand=True)
        self.combo.bind("<<ComboboxSelected>>", lambda e: self._tarjeta_elegida())
        ttk.Button(fila, text="Actualizar", command=self.actualizar_tarjetas).pack(side="left", padx=6)
        self.info = ttk.Label(f1, text="", justify="left")
        self.info.pack(fill="x", padx=6, pady=(0, 6))

        f2 = ttk.LabelFrame(self.raiz, text="2. Particiones")
        f2.pack(fill="x", **p)
        fila = ttk.Frame(f2)
        fila.pack(fill="x", padx=6, pady=4)
        for clave, texto in ESQUEMAS:
            rb = ttk.Radiobutton(fila, text=texto, value=clave, variable=self.esquema, command=self._recalcular)
            rb.pack(side="left", padx=(0, 16))
            if clave == "fat32":
                self.r_fat32 = rb
        fila = ttk.Frame(f2)
        fila.pack(fill="x", padx=6)
        ttk.Label(fila, text="Cantidad:").pack(side="left")
        self.spin = ttk.Spinbox(fila, from_=1, to=8, width=4, textvariable=self.cantidad, command=self._recalcular)
        self.spin.pack(side="left", padx=6)
        self.spin.bind("<KeyRelease>", lambda e: self._recalcular())
        self.max_txt = ttk.Label(fila, text="")
        self.max_txt.pack(side="left", padx=6)
        self.chk_resto = ttk.Checkbutton(f2, text="Usar lo que sobre en una última partición FAT16 (de hasta 4 GB)",
                                         variable=self.resto, command=self._recalcular)
        self.chk_resto.pack(anchor="w", padx=6, pady=2)
        self.plan_txt = ttk.Label(f2, text="", justify="left", font=("Consolas", 9))
        self.plan_txt.pack(fill="x", padx=6, pady=(2, 2))
        self.aviso = ttk.Label(f2, text="", foreground="#b00000", justify="left")
        self.aviso.pack(fill="x", padx=6, pady=(0, 6))

        f3 = ttk.LabelFrame(self.raiz, text="3. Sistema en la partición de arranque")
        f3.pack(fill="x", **p)
        self.f3_fpga = ttk.Frame(f3)
        for clave, (texto, _, _) in contenido.SISTEMAS.items():
            ttk.Radiobutton(self.f3_fpga, text=texto, value=clave, variable=self.sistema,
                            command=self._recalcular).pack(anchor="w", padx=6)
        self.f3_ocm = ttk.Frame(f3)
        fila = ttk.Frame(self.f3_ocm)
        fila.pack(fill="x")
        ttk.Label(fila, text="BIOS (las monta el SD Maker con el pack de KdL; el sistema va con ellas):").pack(
            side="left")
        ttk.Button(fila, text="Opciones de las BIOS...", command=self.opciones_bios).pack(side="right")
        self.bios_txt = ttk.Label(self.f3_ocm, text="", justify="left", font=("Consolas", 9))
        self.bios_txt.pack(anchor="w", pady=(2, 0))
        fo = ttk.LabelFrame(f3, text="Opciones de Nextor 3")
        fo.pack(fill="x", padx=6, pady=(2, 6))
        self.fo = fo
        self.controles_n3 = [
            ttk.Checkbutton(fo, text="Barra invertida en vez de ¥ en las rutas (YENSLASH ON)", variable=self.n3["yenslash"]),
            ttk.Checkbutton(fo, text="Modo inserción al escribir órdenes (BUFINSERT)", variable=self.n3["bufinsert"]),
            ttk.Checkbutton(fo, text="AUTOEXEC.BTM en vez de AUTOEXEC.BAT (admite GOTO, GOSUB y END)",
                            variable=self.n3["btm"]),
        ]
        for c in self.controles_n3:
            c.pack(anchor="w", padx=6)
        fila = ttk.Frame(fo)
        fila.pack(anchor="w", padx=6, pady=(0, 4))
        self.controles_n3.append(ttk.Label(fila, text="Tamaños en DIR:"))
        self.controles_n3.append(ttk.Radiobutton(fila, text="en K desde 10K (Nextor 3)", value="", variable=self.dirk))
        self.controles_n3.append(ttk.Radiobutton(fila, text="en bytes, como MSX-DOS 2", value="0", variable=self.dirk))
        for c in self.controles_n3[-3:]:
            c.pack(side="left", padx=(0, 10))

        f4 = ttk.LabelFrame(self.raiz, text="4. Programas (en la partición de arranque)")
        f4.pack(fill="x", **p)
        self.rej = ttk.Frame(f4)          # las casillas las pone _maquina_elegida (cambian con la maquina)
        self.rej.pack(fill="x", padx=6, pady=4)
        fila = ttk.Frame(f4)
        fila.pack(fill="x", padx=6, pady=(0, 6))
        ttk.Button(fila, text="Todos", command=lambda: self._todos(True)).pack(side="left")
        ttk.Button(fila, text="Ninguno", command=lambda: self._todos(False)).pack(side="left", padx=6)
        ttk.Label(fila, text="Nombre de la tarjeta:").pack(side="left", padx=(24, 4))
        ttk.Entry(fila, textvariable=self.etiqueta, width=14).pack(side="left")

        fila = ttk.Frame(self.raiz)
        fila.pack(fill="x", **p)
        self.b_crear = ttk.Button(fila, text="Preparar la tarjeta", command=self.preparar)
        self.b_crear.pack(side="left")
        self.b_imagen = ttk.Button(fila, text="Guardar como imagen...", command=self.guardar_imagen)
        self.b_imagen.pack(side="left", padx=6)
        ttk.Button(fila, text="Salir", command=self.raiz.destroy).pack(side="right")
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
    def actualizar_tarjetas(self):
        try:
            self.tarjetas = dispositivos.listar_tarjetas()
        except Exception as e:
            self.tarjetas = []
            self.escribir_log("No se pueden listar las tarjetas: %s" % e)
        textos = []
        for t in self.tarjetas:
            unidades = (", " if sys.platform == "darwin" else " ").join(t["letras"])
            unidades = unidades or ("sin volumen" if sys.platform == "darwin" else "sin unidad")
            disco = "disk%d" % t["numero"] if sys.platform == "darwin" else "disco %d" % t["numero"]
            textos.append("%s   %s   %s   (%s, %s)" % (unidades, t["modelo"], formato_tamano(t["bytes"]),
                                                       t["bus"], disco))
        self.combo["values"] = textos
        if textos:
            self.combo.current(0)
        else:
            self.combo.set("No hay ninguna tarjeta SD ni memoria USB extraíble conectada")
        self._tarjeta_elegida()

    def tarjeta(self):
        i = self.combo.current()
        return self.tarjetas[i] if 0 <= i < len(self.tarjetas) else None

    def _tarjeta_elegida(self):
        t = self.tarjeta()
        if t is None:
            self.info["text"] = ""
        else:
            self.info["text"] = "Tamaño: %s (%s sectores de 512 bytes).  Ahora: %s" % (
                formato_tamano(t["bytes"]), format(t["sectores"], ",").replace(",", "."), self._actual(t))
        self._recalcular()

    def _actual(self, t):
        if sys.platform == "darwin":
            partes = t.get("particiones", [])
            if not partes:
                return "sin tabla de particiones"
            return ", ".join("%s de %s" % (p["tipo"], formato_tamano(p["bytes"])) for p in partes)
        if sys.platform != "win32" or not dispositivos.es_admin():
            return "(para ver sus particiones hace falta abrir el programa como administrador)"
        try:
            d = dispositivos.DiscoLectura(t["numero"])
            try:
                tabla = particiones.leer_tabla(lambda lba: d.leer(lba))
            finally:
                d.cerrar()
        except Exception as e:
            return "no se puede leer (%s)" % e
        if not tabla:
            return "sin tabla de particiones"
        return ", ".join("%s de %s" % (particiones.NOMBRES_TIPO.get(tipo, "tipo %02Xh" % tipo),
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
            c.state(["!disabled"] if self._sistema() == "nextor3" else ["disabled"])
        sectores = self._sectores()
        esquema = self.esquema.get()
        fat16 = esquema != "fat32"
        self.spin.state(["!disabled"] if fat16 else ["disabled"])
        self.chk_resto.state(["!disabled"] if fat16 else ["disabled"])
        self.aviso["text"] = AVISO_FAT32 if not fat16 else ""
        if not sectores:
            self.plan_txt["text"] = ""
            self.max_txt["text"] = ""
            return
        self.max_txt["text"] = ""
        if fat16:
            tam = particiones.GB2 if esquema == "fat16-2g" else particiones.GB4
            maximo = particiones.maximo_fat16(sectores, tam)
            self.spin.configure(to=max(1, maximo))
            self.max_txt["text"] = ("caben %d en esta tarjeta (máximo 8: %s)" % (
                maximo, "C: a H: y B: con MAPDRV" if self.maquina.get() == "ocm" else "el menú del MSXimus ve 8")
                                    if maximo else "la tarjeta es más pequeña: una sola partición con toda ella")
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
                uso = "arranque (A:)" if self._sistema() != "ninguno" else ""
            else:
                uso = "%s: (MAPDRV en el AUTOEXEC)" % contenido.UNIDADES[p.numero - 2]
            lineas.append("  %d: %s de %-10s %s" % (p.numero, "FAT32" if p.tipo == particiones.TIPO_FAT32 else "FAT16",
                                                   formato_tamano(p.bytes), uso))
        sobra = particiones.sin_usar(sectores, plan)
        if sobra > 2048:
            lineas.append("  sin usar: %s" % formato_tamano(sobra * 512))
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
        if self._sistema() != "nextor3":
            return ""
        o = self._opciones()
        partes = [contenido.nombre_autoexec("nextor3", o)]
        partes += [t for k, t in (("yenslash", "YENSLASH ON"), ("bufinsert", "BUFINSERT"), ) if o[k]]
        partes.append("DIR en bytes" if o["dirk"] == "0" else "DIR en K")
        return "\nOpciones: " + ", ".join(partes)

    def _bloquear(self, si):
        self.trabajando = si
        for b in (self.b_crear, self.b_imagen):
            b.state(["disabled"] if si else ["!disabled"])

    def _listo_ocm(self):
        if self.maquina.get() != "ocm":
            return True
        if not self.pack:
            messagebox.showwarning("MSX SD Maker", "Para el MSXBOOK hace falta el OCM-SDBIOS Pack de KdL.")
            return False
        return True

    def _texto_sistema(self):
        if self.maquina.get() != "ocm":
            return "Sistema: %s" % contenido.SISTEMAS[self.sistema.get()][0]
        return "BIOS (%s):\n%s" % (self.pack.texto(), "\n".join("    %s  %s" % (n, ocm.describir(r, self.pack))
                                                             for n, r in self.bios))

    def preparar(self):
        if self.trabajando:
            return
        t = self.tarjeta()
        if t is None:
            messagebox.showwarning("MSX SD Maker", "Conecta una tarjeta SD y pulsa Actualizar.")
            return
        if sys.platform == "win32" and not dispositivos.es_admin():
            if messagebox.askyesno("MSX SD Maker", "Para escribir en la tarjeta hace falta abrir el programa como "
                                   "administrador.\n\n¿Lo vuelvo a abrir así?"):
                relanzar_como_admin()
            return
        try:
            plan = self.plan()
        except ValueError as e:
            messagebox.showerror("MSX SD Maker", str(e))
            return
        if not self._listo_ocm():
            return
        unidades = (", " if sys.platform == "darwin" else " ").join(t["letras"])
        unidades = unidades or ("sin volumen" if sys.platform == "darwin" else "sin unidad")
        disco = "disk%d" % t["numero"] if sys.platform == "darwin" else "disco %d" % t["numero"]
        texto = ("Se va a BORRAR TODO lo que hay en:\n\n    %s, %s  (%s, %s)\n\ny se crearán:\n%s\n\n"
                 "%s%s\n\n¿Seguro?" % (t["modelo"], formato_tamano(t["bytes"]), unidades, disco,
                                      self.plan_txt["text"], self._texto_sistema(), self._texto_opciones()))
        if not messagebox.askyesno("MSX SD Maker: borrar la tarjeta", texto, icon="warning", default="no"):
            return

        if sys.platform == "darwin":
            datos_ocm = {"pack": self.pack, "bios": self.bios} if self.maquina.get() == "ocm" else None
            datos = ayudante_macos.datos_trabajo(t, plan, self._sistema(), self._elegidos(),
                                                 self.etiqueta.get() or "MSX", self._opciones(), datos_ocm)
            self._lanzar_macos(datos, "la tarjeta")
            return

        def abrir():
            return dispositivos.Disco(t["numero"])
        self._lanzar(abrir, plan, "la tarjeta")

    def guardar_imagen(self):
        if self.trabajando or not self._listo_ocm():
            return
        # 1.1: el tamano se pregunta siempre (antes, con una tarjeta conectada, la imagen salia del tamano de la tarjeta).
        # 1800M cabe en cualquier tarjeta de 2 GB (las de "2 GB" tienen menos de 2 GiB); en una mayor sobra el resto.
        tam = simpledialog.askstring("MSX SD Maker", "Tamaño de la imagen (por ejemplo 1800M, 3500M o 7G).\n"
                                     "Se puede grabar en una tarjeta de ese tamaño o mayor:\n"
                                     "1800M cabe en cualquiera de 2 GB, 3500M en cualquiera de 4 GB.",
                                     initialvalue="1800M")
        if not tam:
            return
        try:
            t = tam.strip().upper().rstrip("B")
            sectores = int(float(t[:-1]) * {"M": 1 << 20, "G": 1 << 30}[t[-1]]) // 512
        except (ValueError, KeyError, IndexError):
            messagebox.showerror("MSX SD Maker", "Tamaño no válido: %s" % tam)
            return
        ruta = filedialog.asksaveasfilename(title="Guardar la imagen", defaultextension=".img",
                                            filetypes=[("Imagen de disco", "*.img"), ("Todos", "*.*")])
        if not ruta:
            return
        try:
            plan = self.plan(sectores)
        except ValueError as e:
            messagebox.showerror("MSX SD Maker", str(e))
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
                        self.cola.put(("aviso", "al cerrar: %s" % e, None))
        threading.Thread(target=trabajo, daemon=True).start()

    def _lanzar_macos(self, datos, destino):
        self._bloquear(True)
        self.log.delete("1.0", "end")
        self.barra["value"] = 0
        self.estado["text"] = "Esperando la autorización de administrador de macOS..."

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
                    self.estado["text"] = m[1][:110]
                    if m[2] is not None:
                        self.barra["value"] = int(m[2] * 1000)
                    if not m[1].startswith("Copiando"):
                        self.escribir_log(m[1])
                elif m[0] == "fin":
                    self._terminado(m[1], m[2])
                elif m[0] == "error":
                    self._bloquear(False)
                    self.escribir_log("ERROR: " + m[1])
                    messagebox.showerror("MSX SD Maker", "No se ha podido preparar %s:\n\n%s" % (m[2], m[1]))
        except queue.Empty:
            pass
        self.raiz.after(100, self._leer_cola)

    def _terminado(self, inf, destino):
        self._bloquear(False)
        for p in inf["particiones"]:
            self.escribir_log("  particion %d (%s): %s" % (p["numero"], p["etiqueta"], p["geometria"]))
        self.escribir_log("%d ficheros (%s) en %.1f s" % (inf["ficheros"], formato_tamano(inf["bytes"]), inf["segundos"]))
        if inf["errores"]:
            for e in inf["errores"]:
                self.escribir_log("ERROR: " + e)
            messagebox.showerror("MSX SD Maker", "%s está preparada pero la verificación ha encontrado errores:\n\n%s"
                                 % (destino, "\n".join(inf["errores"][:5])))
        else:
            messagebox.showinfo("MSX SD Maker", "%s está lista y verificada.\n\n%d ficheros copiados en la partición "
                                "de arranque." % (destino[:1].upper() + destino[1:], inf["ficheros"]))
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
