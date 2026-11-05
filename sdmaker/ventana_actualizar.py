"""ventana_actualizar.py — el diálogo «Actualizar tarjeta»: enseña lo que lleva una tarjeta ya hecha (sistema, versión,
programas) y lo que se cambiaría, y lo cambia sin formatear y sin borrar ni pisar nada del usuario (actualizar.py).
El análisis y la escritura van en un hilo; los avisos llegan por una cola. Nunca se escribe sin pulsar Actualizar y sin la
confirmación que toque (cambio de sistema, ficheros del usuario que se quieren pisar)."""
import os
import queue
import threading
import tkinter as tk
from tkinter import font as tkfont, messagebox, ttk

from . import actualizar, contenido, idioma
from .actualizar import ACTUALIZAR, ANADIR, CAMBIADO, CONFIG, CONSERVAR, SIN_USO
from .idioma import t as tx

TITULO = "MSX SD Maker"
SI, NO = "[x]", "[ ]"


def elegir_unidad(padre, carpetas, con_sistema):
    """Pregunta cuál de las unidades de la tarjeta es la de arranque. Devuelve la ruta o None si se cancela."""
    top = tk.Toplevel(padre)
    top.title(tx("va.unidad_titulo"))
    top.transient(padre)
    top.resizable(False, False)
    f = ttk.Frame(top, padding=14)
    f.pack(fill="both", expand=True)
    ttk.Label(f, text=tx("va.unidad_info" if con_sistema else "va.unidad_info_sin"), wraplength=460,
              justify="left").pack(anchor="w", pady=(0, 8))
    lista = con_sistema or carpetas
    elegida = tk.StringVar(value=lista[0])
    for c in lista:
        ttk.Radiobutton(f, text=c, value=c, variable=elegida).pack(anchor="w", pady=1)
    resultado = []
    pie = ttk.Frame(f)
    pie.pack(fill="x", pady=(14, 0))
    ttk.Button(pie, text=tx("g.cancelar"), command=top.destroy).pack(side="right")
    ttk.Button(pie, text=tx("g.aceptar"), command=lambda: (resultado.append(elegida.get()), top.destroy())).pack(
        side="right", padx=(0, 8))
    top.grab_set()
    top.wait_window()
    return resultado[0] if resultado else None


class DialogoActualizar:
    """El diálogo. ruta = carpeta raíz de la partición de arranque; pack = el OCM-SDBIOS Pack (ocm.Pack) o None.
    bloquear=False: no espera a que se cierre (para las pruebas de la ventana)."""

    def __init__(self, padre, ruta, pack=None, bloquear=True, carpeta_copias=None, appledouble=None):
        self.ruta, self.pack = ruta, pack
        self.carpeta_copias, self.appledouble = carpeta_copias, appledouble
        self.cola = queue.Queue()
        self.plan = None
        self.ocupado = False
        self.hecho = False
        self.escribible = os.access(ruta, os.W_OK)
        self.toggles = {}               # iid -> ("grupo", clave) | ("forzar", ruta)
        self.claves_destino = []
        self._ultimo_log = None
        self.top = tk.Toplevel(padre)
        self.top.title(tx("va.titulo"))
        self.top.transient(padre)
        self._construir()
        self.top.update_idletasks()
        self.top.minsize(max(760, self.top.winfo_reqwidth()), self.top.winfo_reqheight())
        self.top.after(100, self._leer_cola)
        self._analizar()
        if bloquear:
            self.top.grab_set()
            self.top.wait_window()

    # ------------------------------------------------------------------ ventana
    def _construir(self):
        # filas de la lista tan altas como la letra (con escalado de pantalla el valor por defecto corta las letras)
        ttk.Style(self.top).configure("Act.Treeview", rowheight=tkfont.nametofont("TkDefaultFont").metrics(
            "linespace") + 6)
        f = ttk.Frame(self.top, padding=12)
        f.pack(fill="both", expand=True)
        pie = ttk.Frame(f)          # los botones, abajo del todo: no se pierden si la ventana es baja
        pie.pack(side="bottom", fill="x", pady=(10, 0))
        self.b_cancelar = ttk.Button(pie, text=tx("g.cancelar"), command=self._cerrar)
        self.b_cancelar.pack(side="right")
        self.b_ok = ttk.Button(pie, text=tx("va.actualizar"), command=self._actualizar, state="disabled")
        self.b_ok.pack(side="right", padx=(0, 8))
        ttk.Label(f, text=tx("va.cabecera"), font=("TkDefaultFont", 14, "bold")).pack(anchor="w")
        ttk.Label(f, text=tx("va.sin_formatear"), wraplength=840, justify="left").pack(anchor="w", pady=(2, 8))
        self.resumen = ttk.Label(f, text="", justify="left", wraplength=840)
        self.resumen.pack(anchor="w")
        self.avisos = ttk.Label(f, text="", justify="left", wraplength=840, foreground="#b00000")
        self.fila_destino = ttk.Frame(f)
        self.fila_destino.pack(fill="x", pady=(8, 2))
        fila = self.fila_destino
        ttk.Label(fila, text=tx("va.destino")).pack(side="left")
        self.destino = tk.StringVar()
        self.combo = ttk.Combobox(fila, state="readonly", textvariable=self.destino, width=62)
        self.combo.pack(side="left", padx=8)
        self.combo.bind("<<ComboboxSelected>>", lambda e: self._cambiar_destino())
        self.recomendacion = ttk.Label(f, text="", justify="left", wraplength=840, foreground="#006000")
        cuerpo = ttk.Frame(f)
        cuerpo.pack(fill="both", expand=True, pady=(8, 0))
        self.arbol = ttk.Treeview(cuerpo, columns=("marca", "detalle"), height=11, style="Act.Treeview")
        self.arbol.heading("#0", text=tx("va.col_fichero"))
        self.arbol.heading("marca", text="")
        self.arbol.heading("detalle", text=tx("va.col_detalle"))
        self.arbol.column("#0", width=380, stretch=True)
        self.arbol.column("marca", width=44, stretch=False, anchor="center")
        self.arbol.column("detalle", width=380, stretch=True)
        barra = ttk.Scrollbar(cuerpo, orient="vertical", command=self.arbol.yview)
        self.arbol.configure(yscrollcommand=barra.set)
        self.arbol.pack(side="left", fill="both", expand=True)
        barra.pack(side="left", fill="y")
        self.arbol.bind("<Button-1>", self._clic)
        self.arbol.bind("<space>", lambda e: self._toggle(self.arbol.focus()))
        self.estado = ttk.Label(f, text="")
        self.estado.pack(fill="x", pady=(8, 0))
        self.barra = ttk.Progressbar(f, maximum=1000)
        self.barra.pack(fill="x", pady=(2, 4))
        self.log = tk.Text(f, height=4)
        self.log.pack(fill="x")

    def _cerrar(self):
        if self.ocupado:
            return
        self.top.destroy()

    def _log(self, texto):
        if texto == self._ultimo_log:
            return
        self._ultimo_log = texto
        self.log.insert("end", texto + "\n")
        self.log.see("end")

    def _poner_estado(self, texto, fraccion=None):
        self.estado["text"] = texto[:130]
        if fraccion is not None:
            self.barra["value"] = int(fraccion * 1000)

    def _ocupar(self, si):
        self.ocupado = si
        self.combo.state(["disabled"] if si else ["!disabled"])
        self.b_cancelar.state(["disabled"] if si else ["!disabled"])
        if si:
            self.b_ok.state(["disabled"])

    # ------------------------------------------------------------------ análisis
    def _analizar(self, sistema=None, anadir=(), forzar=()):
        self._ocupar(True)
        self.barra["value"] = 0
        self._poner_estado(tx("va.analizando"))
        aviso = lambda texto, f=None: self.cola.put(("aviso", texto, f))

        def trabajo():
            try:
                plan = actualizar.analizar(self.ruta, sistema=sistema, anadir=anadir, forzar=forzar, pack=self.pack,
                                           aviso=aviso)
                self.cola.put(("plan", plan))
            except Exception as e:
                self.cola.put(("error_analisis", "%s: %s" % (type(e).__name__, e)))
        threading.Thread(target=trabajo, daemon=True).start()

    def _cambiar_destino(self):
        i = self.combo.current()
        if self.plan is None or not 0 <= i < len(self.claves_destino):
            return
        clave = self.claves_destino[i]
        if clave == self.plan.destino:
            return
        anadir = [g for g in self.plan.anadir]
        forzar = [e.ruta for e in self.plan.entradas + self.plan.generados() if e.forzar and not e.obligatorio]
        self._analizar(clave, anadir, forzar)

    def _nombre_destino(self, clave):
        if clave == CONSERVAR:
            return tx("ac.sistema.conservar")
        return actualizar.texto_sistema(clave) + (" " + tx("va.recomendado") if clave == self.plan.recomendado else "")

    def _pintar(self):
        p = self.plan
        L = [tx("va.r_tarjeta", self.ruta), tx("va.r_maquina", tx(contenido.MAQUINAS[p.maquina])),
             tx("va.r_sistema", actualizar.texto_sistema(p.actual[0], p.actual[1]) if p.actual[0]
                else tx("ac.sin_sistema"))]
        if p.maquina == "ocm" and p.ocm and p.ocm["alts"]:
            L.append(tx("va.r_alts", ", ".join("%s: %s" % (n, actualizar.texto_sistema(c) if c else "-")
                                              for n, c in p.ocm["alts"])))
        if p.marca:
            L.append(tx("va.r_marca", p.marca.get("VERSION", "?")))
        elif p.release:
            L.append(tx("va.r_release", p.release))
        if p.marca and p.release:
            L.append(tx("va.r_release", p.release))
        L.append(tx("va.r_programas", ", ".join(actualizar.texto_grupo(g).split(" (")[0] for g in p.lista_grupos
                                               if g in p.presentes) or "-"))
        self.resumen["text"] = "\n".join(L)
        self._texto(self.avisos, "\n".join(p.avisos + ([] if self.escribible else [tx("va.solo_lectura")])), (4, 0))
        self.claves_destino = [CONSERVAR] + [c for c in p.ofrecidos]
        self.combo["values"] = [self._nombre_destino(c) for c in self.claves_destino]
        self.combo.current(self.claves_destino.index(p.destino))
        self._texto(self.recomendacion, tx("va.recomienda_final") if p.recomendado and p.destino != p.recomendado
                    else "", (0, 0), debajo=True)
        self._pintar_arbol()
        self._pintar_sitio()

    def _texto(self, etiqueta, texto, pady, debajo=False):
        """Una etiqueta que solo ocupa sitio si tiene texto (encima o debajo de la fila del sistema de destino)."""
        etiqueta["text"] = texto
        etiqueta.pack_forget()
        if texto:
            etiqueta.pack(anchor="w", pady=pady, **({"after": self.fila_destino} if debajo else
                                                    {"before": self.fila_destino}))

    def _pintar_sitio(self):
        p = self.plan
        confirma = p.confirmacion() is not None and not self.hecho
        if p.libre is not None:
            texto = tx("va.sitio", actualizar.idioma_mb(p.libre), actualizar.idioma_mb(p.bytes_necesarios()))
        else:
            texto = tx("va.sitio_necesario", actualizar.idioma_mb(p.bytes_necesarios()))
        if not p.cabe():
            texto += "  " + tx("va.no_cabe")
        if self.hecho and not p.hay_trabajo():
            texto = tx("va.al_dia")
        self.estado["text"] = texto
        self.barra["value"] = 0
        pendiente = p.hay_trabajo() and p.cabe() and not self.ocupado and self.escribible
        self.b_ok.state(["!disabled"] if pendiente else ["disabled"])
        if confirma and pendiente:
            self.estado["text"] += "  " + tx("va.pide_confirmar")

    def _pintar_arbol(self):
        a = self.arbol
        a.delete(*a.get_children())
        self.toggles = {}
        p = self.plan
        r = p.resumen()
        efectivos = p.grupos_efectivos()

        def padre(texto, lista, abierto=None, detalle=""):
            return a.insert("", "end", text=texto, values=("", detalle),
                            open=len(lista) <= 5 if abierto is None else abierto)

        act = r[ACTUALIZAR]
        if act:
            iid = padre(tx("va.n_actualizar", len(act)), act)
            for e in act:
                a.insert(iid, "end", text=e.ruta, values=("", tx("va.det_regenera" if e.generado else "va.det_antigua")))
        anad = [e for e in r[ANADIR] if e.grupo == "sistema" or e.grupo in efectivos]
        if anad:
            iid = padre(tx("va.n_anadir", len(anad)), anad)
            for e in anad:
                a.insert(iid, "end", text=e.ruta, values=("", tx("va.det_falta")))
        if p.ausentes:
            iid = padre(tx("va.n_nuevos", len(p.ausentes)), p.ausentes, True, tx("va.d_nuevos"))
            for g in p.ausentes:
                ficheros = [e for e in r[ANADIR] if e.grupo == g]
                if not ficheros and g != "flash":
                    continue
                kb = sum(e.tam for e in ficheros) // 1024
                hijo = a.insert(iid, "end", text=actualizar.texto_grupo(g),
                                values=(SI if g in p.anadir else NO, tx("va.det_grupo", len(ficheros), kb)))
                self.toggles[hijo] = ("grupo", g)
        cam = r[CAMBIADO]
        if cam:
            iid = padre(tx("va.n_cambiado", len(cam)), cam, True, tx("va.d_cambiado"))
            for e in cam:
                det = tx("va.det_nuevo_al_lado", e.alt) if e.alt else tx("va.det_se_deja")
                if e.alt and e.alt_ok:
                    det = tx("va.det_ya_al_lado", e.alt)
                hijo = a.insert(iid, "end", text=e.ruta, values=(SI if e.forzar else NO, det))
                self.toggles[hijo] = ("forzar", e.ruta)
        if p.maquina == "ocm" and p.bios_a_cambiar():
            iid = padre(tx("va.n_bios"), [0], True, tx("va.d_bios"))
            a.insert(iid, "end", text=p.ocm["nombre"], values=("", tx("va.det_bios", actualizar.texto_sistema(
                p.actual[0]), actualizar.texto_sistema(p.destino))))
        sin = r[SIN_USO]
        if sin:
            iid = padre(tx("va.n_sin_uso", len(sin)), sin, False, tx("va.d_sin_uso"))
            for e in sin:
                a.insert(iid, "end", text=e.ruta, values=("", tx("va.det_se_queda")))
        cfg = r[CONFIG]
        if cfg:
            iid = padre(tx("va.n_config", len(cfg)), cfg, False, tx("va.d_config"))
            for e in cfg:
                a.insert(iid, "end", text=e.ruta, values=("", tx("va.det_config")))
        if not a.get_children():
            a.insert("", "end", text=tx("va.nada"))

    def _clic(self, evento):
        if self.arbol.identify_region(evento.x, evento.y) == "cell" and self.arbol.identify_column(evento.x) == "#1":
            self._toggle(self.arbol.identify_row(evento.y))

    def _toggle(self, iid):
        if self.ocupado or iid not in self.toggles:
            return
        tipo, dato = self.toggles[iid]
        valor = self.arbol.set(iid, "marca") != SI
        try:
            if tipo == "grupo":
                self.plan.anadir_grupo(dato, valor)
            else:
                self.plan.forzar(dato, valor)
        except ValueError:
            return
        self.arbol.set(iid, "marca", SI if valor else NO)
        if tipo == "grupo":         # lo generado (AUTOEXEC...) depende de los grupos: se vuelve a pintar
            self._pintar_arbol()
        self._pintar_sitio()

    # ------------------------------------------------------------------ escritura
    def _actualizar(self):
        p = self.plan
        if self.ocupado or p is None or not p.hay_trabajo():
            return
        if not p.cabe():
            messagebox.showwarning(TITULO, tx("va.no_cabe_texto"), parent=self.top)
            return
        texto = p.confirmacion()
        if texto and not messagebox.askyesno(tx("va.confirma_titulo"), texto, icon="warning", default="no",
                                             parent=self.top):
            return
        pisar = [e.ruta for e in p.entradas + p.generados() if e.estado == CAMBIADO and e.forzar]
        if pisar and not messagebox.askyesno(tx("va.confirma_titulo"), tx("va.confirma_pisar", len(pisar)),
                                             icon="warning", default="no", parent=self.top):
            return
        p.confirmado = True
        self._ocupar(True)
        self.log.delete("1.0", "end")
        aviso = lambda texto, f=None: self.cola.put(("aviso", texto, f))

        def trabajo():
            try:
                self.cola.put(("informe", actualizar.aplicar(p, aviso, appledouble=self.appledouble,
                                                              carpeta_copias=self.carpeta_copias)))
            except Exception as e:
                self.cola.put(("error_aplicar", "%s: %s" % (type(e).__name__, e)))
        threading.Thread(target=trabajo, daemon=True).start()

    def _leer_cola(self):
        try:
            while True:
                m = self.cola.get_nowait()
                if m[0] == "aviso":
                    self._poner_estado(m[1], m[2])
                    if not m[1].startswith(idioma.prefijos("ac.copiando")):
                        self._log(m[1])
                elif m[0] == "plan":
                    self.plan = m[1]
                    self._ocupar(False)
                    self._pintar()
                elif m[0] == "error_analisis":
                    self._ocupar(False)
                    self._poner_estado(tx("va.error_analisis"))
                    self._log("ERROR: " + m[1])
                    messagebox.showerror(TITULO, tx("va.error_analisis_texto", m[1]), parent=self.top)
                elif m[0] == "informe":
                    self._terminado(m[1])
                elif m[0] == "error_aplicar":
                    self._ocupar(False)
                    self._log("ERROR: " + m[1])
                    messagebox.showerror(TITULO, tx("va.error_aplicar", m[1]), parent=self.top)
                    self._analizar()
        except queue.Empty:
            pass
        if self.top.winfo_exists():
            self.top.after(100, self._leer_cola)

    def _terminado(self, inf):
        self.hecho = True
        for linea in inf.texto().splitlines():
            self._log(linea)
        self._ocupar(False)
        texto = tx("va.fin_ok", len(inf.actualizados) + len(inf.forzados), len(inf.anadidos), len(inf.dejados))
        if inf.reinicio:
            texto += "\n\n" + tx("ac.i.reinicio")
        texto += "\n\n" + tx("va.expulsar")
        if inf.errores:
            messagebox.showerror(TITULO, tx("va.fin_errores", "\n".join(inf.errores[:5])) + "\n\n" + texto,
                                 parent=self.top)
        else:
            messagebox.showinfo(TITULO, texto, parent=self.top)
        self.b_cancelar["text"] = tx("va.cerrar")
        self._analizar(self.plan.destino)       # lo que queda ahora: debería ser nada que hacer


def abrir(padre, ruta, pack=None, **kw):
    return DialogoActualizar(padre, ruta, pack, **kw)
