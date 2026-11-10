"""ventana_zynq.py — la ventana del programa de la tarjeta de arranque (TF1) de la MSXimus Z (MSXimusZboot.py).

Tres pasos en una sola ventana (la tarjeta, la version de msx.barcelona o un BOOT.bin propio, y el formato), un boton
que lo hace todo (bajar y comprobar, formatear, copiar, releer) y, al acabar, la ventana de los pasos de la instalacion
con SW1 antes y despues y la foto de la ranura TF1. Escribir la tarjeta necesita administrador: en Windows el .exe lo
pide al abrirse; en macOS lo pide una copia del programa con el dialogo del sistema (zynq_boot.lanzar_macos)."""
import os
import queue
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from . import dispositivos, idioma, zynq_boot
from .dispositivos import formato_tamano

tx = idioma.t


def recurso(*partes):
    """Ruta de un fichero de datos (carpeta zynq/ junto al programa, o dentro del .exe/.app de PyInstaller)."""
    base = getattr(sys, "_MEIPASS", None) or os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
    return os.path.join(base, "zynq", *partes)


# ------------------------------------------------------------------ SW1 dibujado
def dibujar_sw1(canvas, x, y, palancas, escala=1.0):
    """Un DIP de 2 posiciones. palancas = (True/False, True/False): True = hacia ON (arriba)."""
    e = escala
    ancho, alto = 120 * e, 92 * e
    canvas.create_rectangle(x, y, x + ancho, y + alto, fill="#c62828", outline="#7f1010", width=2)
    rotulo = canvas.create_text(x + 6 * e, y + 4 * e, text="ON", anchor="nw", fill="white",
                                font=("Segoe UI", 10, "bold"))          # el tamano de letra ya escala con el DPI
    bx = canvas.bbox(rotulo)[2] + 5 * e
    canvas.create_line(bx, y + 20 * e, bx, y + 5 * e, fill="white", width=2, arrow="last")
    for i, arriba in enumerate(palancas):
        cx = x + (40 + i * 46) * e
        canvas.create_rectangle(cx, y + 22 * e, cx + 28 * e, y + 72 * e, fill="#f5f5f5", outline="#555555")
        py = y + 24 * e if arriba else y + 46 * e
        canvas.create_rectangle(cx + 3 * e, py, cx + 25 * e, py + 24 * e, fill="#263238", outline="#263238")
        canvas.create_text(cx + 14 * e, y + 83 * e, text=str(i + 1), fill="white", font=("Segoe UI", 10, "bold"))
    for i, arriba in enumerate(palancas):
        cx = x + (40 + i * 46) * e
        canvas.create_text(cx + 14 * e, y + alto + 12 * e, text="ON" if arriba else "OFF",
                           font=("Segoe UI", 10, "bold"), fill="#1b5e20" if arriba else "#333333")


def ventana_pasos(raiz):
    """La explicacion de la instalacion: SW1 antes y despues, la ranura TF1 y los pasos en la placa."""
    top = tk.Toplevel(raiz)
    top.title(tx("zp.titulo"))
    top.resizable(False, False)
    marco = ttk.Frame(top, padding=14)
    marco.pack(fill="both", expand=True)
    arriba = ttk.Frame(marco)
    arriba.pack(fill="x")
    fotos = []
    for col, (clave, palancas, foto) in enumerate((("zp.antes", (False, False), "sw1_sd.png"),
                                                   ("zp.despues", (True, False), "sw1_qspi.png"))):
        f = ttk.Frame(arriba, padding=(0, 0, 18, 0))
        f.grid(row=0, column=col, sticky="n")
        ttk.Label(f, text=tx(clave), font=("Segoe UI", 10, "bold"), justify="center").pack()
        ruta = recurso(foto)
        if os.path.isfile(ruta):
            img = tk.PhotoImage(file=ruta)
            fotos.append(img)
            ttk.Label(f, image=img).pack(pady=6)
        else:
            e = max(1.0, f.winfo_fpixels("1i") / 96.0)       # pantallas con escalado (125 %, 150 %...)
            c = tk.Canvas(f, width=int(170 * e), height=int(130 * e), highlightthickness=0, background="white")
            c.pack(pady=6)
            dibujar_sw1(c, 25 * e, 8 * e, palancas, e)
    ruta = recurso("tf1-ranura.png")
    f = ttk.Frame(arriba)
    f.grid(row=0, column=2, sticky="n")
    if os.path.isfile(ruta):
        img = tk.PhotoImage(file=ruta)
        fotos.append(img)
        ttk.Label(f, image=img).pack()
    ttk.Label(f, text=tx("zp.foto_tf1"), wraplength=330, justify="left").pack(pady=(4, 0))
    top.fotos = fotos
    ttk.Label(marco, text=tx("zp.dibujo"), wraplength=900, justify="left", foreground="#555555").pack(anchor="w",
                                                                                                     pady=(8, 8))
    ttk.Label(marco, text=tx("zp.pasos"), justify="left", font=("Segoe UI", 10)).pack(anchor="w")
    ttk.Label(marco, text=tx("zp.negro"), wraplength=900, justify="left", foreground="#8a4b00").pack(anchor="w",
                                                                                                    pady=(10, 0))
    ttk.Button(marco, text=tx("zp.cerrar"), command=top.destroy).pack(anchor="e", pady=(12, 0))
    top.transient(raiz)
    top.focus_set()
    return top


# ------------------------------------------------------------------ la ventana
class Ventana:
    def __init__(self, raiz):
        self.raiz = raiz
        self.cola = queue.Queue()
        self.tarjetas = []
        self.manifiestos = {}          # canal -> dict
        self.errores_canal = {}
        self.boot_propio = None        # ruta de un BOOT.bin del ordenador
        self.trabajando = False
        self.construir()
        self.actualizar_tarjetas()
        threading.Thread(target=self._bajar_manifiestos, daemon=True).start()
        self.raiz.after(100, self._leer_cola)

    # ---------------------------------------------------------------- interfaz
    def construir(self):
        r = self.raiz
        for w in r.winfo_children():
            w.destroy()
        r.title("%s  %s" % (tx("zv.titulo"), zynq_boot.VERSION_PROGRAMA))
        m = ttk.Frame(r, padding=14)
        m.pack(fill="both", expand=True)

        cab = ttk.Frame(m)
        cab.pack(fill="x")
        ttk.Label(cab, text="MSXimus Z", font=("Segoe UI", 16, "bold")).pack(side="left")
        self.lang = tk.StringVar(value=idioma.actual())
        sel = ttk.Combobox(cab, state="readonly", width=10, values=[n for _, n in idioma.IDIOMAS])
        sel.set(dict(idioma.IDIOMAS)[idioma.actual()])
        sel.pack(side="right")
        sel.bind("<<ComboboxSelected>>", lambda e: self._cambiar_idioma(sel.get()))
        ttk.Label(m, text=tx("zv.intro"), wraplength=860, justify="left").pack(anchor="w", pady=(6, 10))

        # 1. la tarjeta
        f1 = ttk.LabelFrame(m, text=tx("zv.paso1"), padding=10)
        f1.pack(fill="x")
        self.combo_tarjeta = ttk.Combobox(f1, state="readonly", width=70)
        self.combo_tarjeta.pack(side="left", fill="x", expand=True)
        ttk.Button(f1, text=tx("zv.refrescar"), command=self.actualizar_tarjetas).pack(side="left", padx=(8, 0))

        # 2. la version
        f2 = ttk.LabelFrame(m, text=tx("zv.paso2"), padding=10)
        f2.pack(fill="x", pady=(10, 0))
        self.origen = tk.StringVar(value="")
        self.marco_canales = ttk.Frame(f2)
        self.marco_canales.pack(fill="x")
        fv = ttk.Frame(f2)
        fv.pack(fill="x", pady=(8, 0))
        ttk.Label(fv, text=tx("zv.variante")).pack(side="left")
        lang = "es" if idioma.actual() == "es" else "en"
        self.nombres_var = [(v, zynq_boot.NOMBRE_VARIANTE[lang][v]) for v in zynq_boot.VARIANTES]
        self.combo_var = ttk.Combobox(fv, state="readonly", width=36, values=[n for _, n in self.nombres_var])
        self.combo_var.current(0 if lang == "es" else 2)
        self.combo_var.pack(side="left", padx=(6, 8))
        ttk.Label(fv, text=tx("zv.variante_nota"), foreground="#555555").pack(side="left")
        self.notas = ttk.Label(f2, text="", foreground="#555555", wraplength=840, justify="left")
        self.notas.pack(anchor="w", pady=(6, 0))
        self._pintar_canales()

        # 3. formato
        f3 = ttk.LabelFrame(m, text=tx("zv.paso3"), padding=10)
        f3.pack(fill="x", pady=(10, 0))
        self.esquema = tk.StringVar(value="fat32")
        ttk.Radiobutton(f3, text=tx("zv.fat32"), value="fat32", variable=self.esquema).pack(side="left")
        ttk.Radiobutton(f3, text=tx("zv.fat16"), value="fat16", variable=self.esquema).pack(side="left", padx=(16, 0))

        # botones, progreso
        fb = ttk.Frame(m)
        fb.pack(fill="x", pady=(14, 0))
        self.boton = ttk.Button(fb, text=tx("zv.preparar"), command=self.preparar)
        self.boton.pack(side="left")
        self.boton_img = ttk.Button(fb, text=tx("zv.imagen"), command=self.guardar_imagen)
        self.boton_img.pack(side="left", padx=(8, 0))
        ttk.Button(fb, text=tx("zv.como"), command=lambda: ventana_pasos(self.raiz)).pack(side="right")
        self.barra = ttk.Progressbar(m, maximum=1000)
        self.barra.pack(fill="x", pady=(12, 0))
        self.estado = ttk.Label(m, text=tx("zv.listo"), foreground="#333333")
        self.estado.pack(anchor="w", pady=(4, 0))

    def _cambiar_idioma(self, nombre):
        lang = {n: c for c, n in idioma.IDIOMAS}[nombre]
        idioma.fijar(lang, recordar=True)
        origen = self.origen.get()
        self.construir()
        self.origen.set(origen)
        self._pintar_canales()
        self._pintar_tarjetas()

    def _pintar_canales(self):
        for w in self.marco_canales.winfo_children():
            w.destroy()
        if not self.manifiestos and not self.errores_canal:
            ttk.Label(self.marco_canales, text=tx("zv.cargando")).pack(anchor="w")
        for canal, _ in zynq_boot.CANALES:
            d = self.manifiestos.get(canal)
            if d:
                clave = "zv.canal_oficial" if canal == "oficial" else "zv.canal_beta"
                ttk.Radiobutton(self.marco_canales, text=tx(clave, d["version"], d.get("fecha", "")), value=canal,
                                variable=self.origen, command=self._pintar_notas).pack(anchor="w")
            elif canal in self.errores_canal:
                nombre = tx("zv.oficial") if canal == "oficial" else tx("zv.beta")
                ttk.Label(self.marco_canales, text=tx("zv.canal_error", nombre, self.errores_canal[canal]),
                          foreground="#a00000").pack(anchor="w")
        texto = tx("zv.propio_elegido", os.path.basename(self.boot_propio)) if self.boot_propio else tx("zv.propio")
        ttk.Radiobutton(self.marco_canales, text=texto, value="propio", variable=self.origen,
                        command=self._elegir_propio).pack(anchor="w", pady=(4, 0))
        if not self.origen.get() and "oficial" in self.manifiestos:
            self.origen.set("oficial")
        self._pintar_notas()

    def _pintar_notas(self):
        d = self.manifiestos.get(self.origen.get())
        self.notas["text"] = tx("zv.notas", " · ".join(d["notas"])) if d and d["notas"] else ""

    def _elegir_propio(self):
        ruta = filedialog.askopenfilename(title=tx("zv.boot_titulo"),
                                          filetypes=[(tx("zv.boot_tipo"), "*.bin"), (tx("g.todos_archivos"), "*.*")])
        if ruta:
            try:
                with open(ruta, "rb") as f:
                    info = zynq_boot.info_boot(f.read(zynq_boot.IMG_MAX + 1))
            except (OSError, ValueError) as e:
                messagebox.showerror(tx("zv.titulo"), tx("zv.boot_malo", e))
                ruta = None
            else:
                if info.get("version"):
                    self.estado["text"] = tx("zv.version_boot", info.get("version"), info.get("variante", "?"))
        self.boot_propio = ruta or self.boot_propio
        if not self.boot_propio:
            self.origen.set("oficial" if "oficial" in self.manifiestos else "")
        self._pintar_canales()

    def _pintar_tarjetas(self):
        if not self.tarjetas:
            self.combo_tarjeta["values"] = [tx("zv.sin_tarjetas")]
            self.combo_tarjeta.current(0)
            return
        vals = []
        for t in self.tarjetas:
            unidades = ", ".join(t.get("letras") or []) or "-"
            vals.append(tx("zv.tarjeta_txt", unidades, formato_tamano(t["bytes"]), t["modelo"]))
        self.combo_tarjeta["values"] = vals
        self.combo_tarjeta.current(0)

    def actualizar_tarjetas(self):
        try:
            self.tarjetas = dispositivos.listar_tarjetas()
        except Exception as e:
            self.tarjetas = []
            self.estado["text"] = str(e)
        self._pintar_tarjetas()

    def tarjeta(self):
        if not self.tarjetas:
            return None
        i = self.combo_tarjeta.current()
        return self.tarjetas[i] if 0 <= i < len(self.tarjetas) else None

    def variante(self):
        return self.nombres_var[max(0, self.combo_var.current())][0]

    # ---------------------------------------------------------------- red
    def _bajar_manifiestos(self):
        self.cola.put(("manifiestos", zynq_boot.bajar_manifiestos()))

    # ---------------------------------------------------------------- trabajo
    def _bloquear(self, si):
        self.trabajando = si
        for b in (self.boton, self.boton_img):
            b["state"] = "disabled" if si else "normal"

    def _aviso(self, texto, fraccion=None):
        self.cola.put(("aviso", texto, fraccion))

    def _origen_listo(self):
        o = self.origen.get()
        if o == "propio" and self.boot_propio:
            return True
        if o in self.manifiestos:
            return True
        messagebox.showwarning(tx("zv.titulo"), tx("zv.elige_version"))
        return False

    def _descripcion(self):
        o = self.origen.get()
        if o == "propio":
            return os.path.basename(self.boot_propio)
        d = self.manifiestos[o]
        return "%s %s (%s)" % (tx("zv.oficial") if o == "oficial" else tx("zv.beta"), d["version"],
                               dict(self.nombres_var)[self.variante()])

    def _como_conseguir_boot(self):
        """En el hilo PRINCIPAL (Tk no se toca desde otro hilo): una funcion que, ya en el hilo de trabajo, devuelve la
        ruta del BOOT.bin (bajado y comprobado, o el propio)."""
        o, propio, variante = self.origen.get(), self.boot_propio, self.variante()
        if o == "propio":
            return lambda: propio
        manifiesto = self.manifiestos[o]
        return lambda: zynq_boot.bajar_imagen(manifiesto, variante, self._aviso)

    def preparar(self):
        if self.trabajando:
            return
        t = self.tarjeta()
        if t is None:
            messagebox.showwarning(tx("zv.titulo"), tx("zv.elige_tarjeta"))
            return
        if not self._origen_listo():
            return
        if sys.platform == "win32" and not dispositivos.es_admin():
            if messagebox.askyesno(tx("zv.titulo"), tx("zv.admin")):
                relanzar_como_admin()
            return
        try:
            plan = zynq_boot.planificar(t["sectores"], self.esquema.get())
        except ValueError as e:
            messagebox.showerror(tx("zv.titulo"), str(e))
            return
        destino = tx("zv.tarjeta_txt", ", ".join(t.get("letras") or []) or "-", formato_tamano(t["bytes"]),
                     t["modelo"])
        if not messagebox.askyesno(tx("zv.borrar_titulo"),
                                   tx("zv.borrar", destino, "FAT32" if self.esquema.get() == "fat32" else "FAT16",
                                      self._descripcion()), icon="warning", default="no"):
            return
        self._lanzar(lambda: dispositivos.Disco(t["numero"]), plan, tarjeta=t)

    def guardar_imagen(self):
        if self.trabajando or not self._origen_listo():
            return
        ruta = filedialog.asksaveasfilename(title=tx("zv.imagen_titulo"), defaultextension=".img",
                                            initialfile="MSXimusZ_TF1.img",
                                            filetypes=[(tx("zv.imagen_tipo"), "*.img"), (tx("g.todos_archivos"), "*.*")])
        if not ruta:
            return
        sectores = (1000 << 20) // 512          # 1000 MiB: cabe en cualquier tarjeta de 1 GB
        try:
            plan = zynq_boot.planificar(sectores, self.esquema.get())
        except ValueError as e:
            messagebox.showerror(tx("zv.titulo"), str(e))
            return
        self._lanzar(lambda: dispositivos.Imagen(ruta, sectores), plan, imagen=ruta)

    def _lanzar(self, abrir, plan, tarjeta=None, imagen=None):
        self._bloquear(True)
        self.barra["value"] = 0
        macos = tarjeta is not None and sys.platform == "darwin"
        conseguir_boot = self._como_conseguir_boot()

        def trabajo():
            dev = None
            try:
                ruta = conseguir_boot()
                if macos:
                    self._aviso(tx("zv.esperando_admin"), 0.32)
                    inf = zynq_boot.lanzar_macos(zynq_boot.datos_trabajo(tarjeta, plan, ruta), self._aviso)
                else:
                    with open(ruta, "rb") as f:
                        boot = f.read(zynq_boot.IMG_MAX + 1)
                    dev = abrir()
                    inf = zynq_boot.crear(dev, plan, boot, aviso=self._aviso)
                self.cola.put(("fin", inf, imagen))
            except Exception as e:
                self.cola.put(("error", "%s: %s" % (type(e).__name__, e)))
            finally:
                if dev is not None:
                    try:
                        dev.cerrar()
                    except Exception as e:
                        self.cola.put(("aviso", str(e), None))
        threading.Thread(target=trabajo, daemon=True).start()

    def _leer_cola(self):
        try:
            while True:
                m = self.cola.get_nowait()
                if m[0] == "manifiestos":
                    for canal, d, err in m[1]:
                        if d:
                            self.manifiestos[canal] = d
                        else:
                            self.errores_canal[canal] = err
                    self._pintar_canales()
                elif m[0] == "aviso":
                    self.estado["text"] = m[1][:120]
                    if m[2] is not None:
                        self.barra["value"] = int(m[2] * 1000)
                elif m[0] == "fin":
                    self._bloquear(False)
                    inf, imagen = m[1], m[2]
                    if inf["errores"]:
                        messagebox.showerror(tx("zv.titulo"), tx("zv.fin_errores", "\n".join(inf["errores"][:5])))
                    elif imagen:
                        messagebox.showinfo(tx("zv.titulo"), tx("zv.imagen_ok", imagen))
                    else:
                        messagebox.showinfo(tx("zv.titulo"), tx("zv.fin_ok", "BOOT.bin"))
                        ventana_pasos(self.raiz)
                    self.raiz.after(2500, self.actualizar_tarjetas)
                elif m[0] == "error":
                    self._bloquear(False)
                    self.estado["text"] = m[1][:120]
                    messagebox.showerror(tx("zv.titulo"), tx("zv.error", m[1]))
        except queue.Empty:
            pass
        self.raiz.after(100, self._leer_cola)


def relanzar_como_admin():
    import ctypes
    if getattr(sys, "frozen", False):
        exe, params = sys.executable, ""
    else:
        exe, params = sys.executable, '"%s"' % os.path.abspath(sys.argv[0])
    ctypes.windll.shell32.ShellExecuteW(None, "runas", exe, params, None, 1)
    sys.exit(0)


def main():
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass
    raiz = tk.Tk()
    try:
        estilo = ttk.Style()
        estilo.theme_use("vista" if sys.platform == "win32" else "aqua" if sys.platform == "darwin" else "clam")
        raiz.configure(background=estilo.lookup("TFrame", "background"))
    except tk.TclError:
        pass
    Ventana(raiz)
    raiz.mainloop()
