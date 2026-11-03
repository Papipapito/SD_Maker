"""Ventana del creador de ROM Nextor 3."""
import hashlib
import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from . import contenido, nextor_bios
from .idioma import t as tx
from .ventana_ocm import DialogoFileHunter


class DialogoPack:
    """Editor por bloques del pack fijo de 512 KB de MSXnano/MSXimus."""

    def __init__(self, padre, ruta, base):
        self.ruta = ruta
        self.base = base
        with open(ruta, "rb") as f:
            self.original = f.read()
        nextor_bios.bloques_pack(self.original)       # valida antes de construir la ventana
        self.pack_base = self.original
        self.reemplazos = {}
        self.estado = {}
        self.top = tk.Toplevel(padre)
        self.top.title(tx("vn.pack_titulo"))
        self.top.transient(padre)
        self.top.resizable(False, False)
        self._construir()
        self.top.grab_set()
        self.top.wait_window()

    def _construir(self):
        f = ttk.Frame(self.top, padding=14)
        f.pack(fill="both", expand=True)
        ttk.Label(f, text=tx("vn.pack_cabecera"), font=("Segoe UI", 14, "bold")).grid(
            row=0, column=0, columnspan=5, sticky="w")
        ttk.Label(f, text=os.path.basename(self.ruta), foreground="#666666").grid(
            row=1, column=0, columnspan=5, sticky="w", pady=(2, 8))
        ttk.Label(f, text=tx("vn.pack_info"), wraplength=760, justify="left").grid(
            row=2, column=0, columnspan=5, sticky="w", pady=(0, 10))
        ttk.Label(f, text=tx("vn.col_bloque"), font=("Segoe UI", 9, "bold")).grid(row=3, column=0, sticky="w")
        ttk.Label(f, text=tx("vn.col_posicion"), font=("Segoe UI", 9, "bold")).grid(row=3, column=1, sticky="w")
        ttk.Label(f, text=tx("vn.col_estado"), font=("Segoe UI", 9, "bold")).grid(row=3, column=2, sticky="w")
        for fila, (clave, nombre, offset, tamano, editable, datos) in enumerate(
                nextor_bios.bloques_pack(self.original), 4):
            ttk.Label(f, text=tx(nombre)).grid(row=fila, column=0, sticky="w", pady=3)
            ttk.Label(f, text="%05Xh · %d KB" % (offset, tamano // 1024)).grid(
                row=fila, column=1, sticky="w", padx=(12, 16))
            estado = ttk.Label(f, text=self._hash(datos), width=19)
            estado.grid(row=fila, column=2, sticky="w")
            self.estado[clave] = estado
            if clave == "nextor":
                ttk.Button(f, text=tx("vn.nextor_final"), command=self._nextor_final).grid(
                    row=fila, column=3, columnspan=2, sticky="ew", padx=(8, 0))
            elif editable:
                ttk.Button(f, text=tx("g.archivo"), command=lambda c=clave, t=tamano: self._archivo(c, t)).grid(
                    row=fila, column=3, padx=(8, 0))
                ttk.Button(f, text="File-Hunter…", command=lambda c=clave, n=nombre, t=tamano:
                           self._filehunter(c, n, t)).grid(row=fila, column=4, padx=(6, 0))
            else:
                ttk.Label(f, text=tx("vn.protegido"), foreground="#777777").grid(
                    row=fila, column=3, columnspan=2, sticky="w", padx=(8, 0))
        aviso_fila = 4 + len(nextor_bios.PACK_BLOCKS)
        ttk.Label(f, text=tx("vn.pack_aviso"), wraplength=760, justify="left", foreground="#9a5400").grid(
            row=aviso_fila, column=0, columnspan=5, sticky="w", pady=(10, 4))
        pie = ttk.Frame(f)
        pie.grid(row=aviso_fila + 1, column=0, columnspan=5, sticky="ew", pady=(12, 0))
        ttk.Button(pie, text=tx("g.cancelar"), command=self.top.destroy).pack(side="right")
        ttk.Button(pie, text=tx("vn.guardar_pack"), command=self._guardar).pack(
            side="right", padx=(0, 8))
        ttk.Button(pie, text=tx("vn.restaurar"), command=self._restaurar).pack(side="left")

    @staticmethod
    def _hash(datos):
        return hashlib.sha256(datos).hexdigest()[:12]

    def _poner(self, clave, ruta, tamano):
        try:
            with open(ruta, "rb") as f:
                datos = f.read()
        except OSError as e:
            messagebox.showerror(tx("vn.err_leer"), str(e), parent=self.top)
            return
        if len(datos) != tamano:
            messagebox.showerror(tx("vn.tam_incompatible"), tx("vn.tam_incompatible_texto", os.path.basename(ruta),
                                                               len(datos), tamano), parent=self.top)
            return
        if clave == "music_menu" and not messagebox.askyesno(
                tx("vn.menu_titulo"), tx("vn.menu_texto"), parent=self.top):
            return
        self.reemplazos[clave] = datos
        self.estado[clave]["text"] = self._hash(datos) + tx("vn.modificado")

    def _archivo(self, clave, tamano):
        ruta = filedialog.askopenfilename(parent=self.top, title=tx("vn.elegir_rom", tamano // 1024),
                                          filetypes=[(tx("vn.tipo_rom"), "*.rom *.bin"), (tx("g.todos"), "*")])
        if ruta:
            self._poner(clave, ruta, tamano)

    def _filehunter(self, clave, nombre, tamano):
        d = DialogoFileHunter(self.top, tamano_kb=tamano // 1024, contexto=tx("vn.contexto_bloque", tx(nombre)))
        if d.resultado:
            self._poner(clave, d.resultado, tamano)

    def _nextor_final(self):
        try:
            with open(self.base, "rb") as f:
                base = f.read()
            self.pack_base = nextor_bios.actualizar_pack_bios(self.pack_base, base)
        except (OSError, ValueError) as e:
            messagebox.showerror(tx("vn.err_nextor"), str(e), parent=self.top)
            return
        datos = self.pack_base[nextor_bios.PACK_NEXTOR_OFFSET:
                               nextor_bios.PACK_NEXTOR_OFFSET + nextor_bios.PACK_NEXTOR_SIZE]
        self.estado["nextor"]["text"] = self._hash(datos) + "  3.0 final"

    def _restaurar(self):
        self.pack_base = self.original
        self.reemplazos.clear()
        for clave, _, _, _, _, datos in nextor_bios.bloques_pack(self.original):
            self.estado[clave]["text"] = self._hash(datos)

    def _guardar(self):
        nombre, ext = os.path.splitext(os.path.basename(self.ruta))
        destino = filedialog.asksaveasfilename(parent=self.top, title=tx("vn.guardar_titulo"),
                                               initialfile=nombre + "_personalizado" + (ext or ".bin"),
                                               defaultextension=".bin",
                                               filetypes=[(tx("vn.tipo_pack"), "*.bin"), (tx("g.todos"), "*")])
        if not destino:
            return
        try:
            datos = nextor_bios.personalizar_pack(self.pack_base, self.reemplazos)
            with open(destino, "wb") as f:
                f.write(datos)
        except (OSError, ValueError) as e:
            messagebox.showerror(tx("vn.err_guardar"), str(e), parent=self.top)
            return
        messagebox.showinfo(tx("vn.pack_creado"), tx("vn.pack_creado_texto", destino), parent=self.top)
        self.top.destroy()


class Dialogo:
    def __init__(self, padre):
        self.top = tk.Toplevel(padre)
        self.top.title(tx("vn.titulo"))
        self.top.transient(padre)
        self.top.resizable(False, False)
        self.rutas = {k: tk.StringVar() for k in ("driver", "mapper", "extra")}
        self.direccion = tk.StringVar()
        self.teclas = tk.StringVar()
        self._construir()
        self.top.grab_set()
        self.top.wait_window()

    def _construir(self):
        f = ttk.Frame(self.top, padding=16)
        f.pack(fill="both", expand=True)
        ttk.Label(f, text=tx("vn.cabecera"), font=("Segoe UI", 14, "bold")).grid(
            row=0, column=0, columnspan=3, sticky="w")
        ttk.Label(f, text=tx("vn.info"), wraplength=620, justify="left").grid(
            row=1, column=0, columnspan=3, sticky="w", pady=(4, 14))

        pack = ttk.LabelFrame(f, text=tx("vn.marco_pack"))
        pack.grid(row=2, column=0, columnspan=3, sticky="ew", pady=(0, 14))
        ttk.Label(pack, text=tx("vn.marco_info"), wraplength=430,
                  justify="left").pack(side="left", padx=10, pady=9)
        botones_pack = ttk.Frame(pack)
        botones_pack.pack(side="right", padx=10, pady=9)
        ttk.Button(botones_pack, text=tx("vn.personalizar"), command=self._personalizar_pack).pack(anchor="e")
        ttk.Button(botones_pack, text=tx("vn.solo_nextor"), command=self._actualizar_pack).pack(
            anchor="e", pady=(5, 0))

        base = os.path.join(contenido.carpeta_sd(), "nextor-3.0.0", "Nextor-3.0.0.base.dat")
        ttk.Separator(f).grid(row=3, column=0, columnspan=3, sticky="ew", pady=(0, 10))
        ttk.Label(f, text=tx("vn.avanzada"), font=("Segoe UI", 11, "bold")).grid(
            row=4, column=0, columnspan=3, sticky="w", pady=(0, 5))
        ttk.Label(f, text=tx("vn.kernel")).grid(row=5, column=0, sticky="w", pady=4)
        ttk.Label(f, text=base, foreground="#666666", wraplength=490).grid(row=5, column=1, columnspan=2, sticky="w")
        self.base = base

        filas = (("driver", tx("vn.driver"), True), ("mapper", tx("vn.mapper"), False),
                 ("extra", tx("vn.extra"), False))
        for fila, (clave, texto, obligatorio) in enumerate(filas, 6):
            ttk.Label(f, text=texto + (" *" if obligatorio else tx("vn.opcional"))).grid(row=fila, column=0, sticky="w",
                                                                                          pady=4)
            ttk.Entry(f, textvariable=self.rutas[clave], width=56, state="readonly").grid(
                row=fila, column=1, sticky="ew", padx=(10, 8), pady=4)
            ttk.Button(f, text=tx("vn.elegir"), command=lambda c=clave: self._elegir(c)).grid(row=fila, column=2, pady=4)

        ttk.Label(f, text=tx("vn.mapper8k")).grid(row=9, column=0, sticky="w", pady=4)
        ttk.Entry(f, textvariable=self.direccion, width=12).grid(row=9, column=1, sticky="w", padx=(10, 0), pady=4)
        ttk.Label(f, text=tx("vn.mapper8k_ayuda"), foreground="#666666").grid(
            row=9, column=1, columnspan=2, sticky="e")
        ttk.Label(f, text=tx("vn.teclas")).grid(row=10, column=0, sticky="w", pady=4)
        ttk.Entry(f, textvariable=self.teclas, width=12).grid(row=10, column=1, sticky="w", padx=(10, 0), pady=4)
        ttk.Label(f, text=tx("vn.teclas_ayuda"), foreground="#666666").grid(
            row=10, column=1, columnspan=2, sticky="e")

        ttk.Label(f, text=tx("vn.nota_driver"), wraplength=620, foreground="#7a4c00", justify="left").grid(
            row=11, column=0, columnspan=3, sticky="w", pady=(12, 6))
        pie = ttk.Frame(f)
        pie.grid(row=12, column=0, columnspan=3, sticky="e", pady=(10, 0))
        ttk.Button(pie, text=tx("g.cancelar"), command=self.top.destroy).pack(side="right")
        ttk.Button(pie, text=tx("vn.crear_rom"), command=self._crear).pack(side="right", padx=(0, 8))

    def _elegir(self, clave):
        tipos = ((tx("vn.tipo_driver"), "*.bin *.drv *.rom"), (tx("g.todos_archivos"), "*"))
        ruta = filedialog.askopenfilename(parent=self.top, title=tx("vn.elegir_clave", clave), filetypes=tipos)
        if ruta:
            self.rutas[clave].set(ruta)

    def _personalizar_pack(self):
        origen = filedialog.askopenfilename(parent=self.top, title=tx("vn.elegir_pack"),
                                            filetypes=[(tx("vn.tipo_pack"), "*.bin"), (tx("g.todos_archivos"), "*")])
        if not origen:
            return
        try:
            DialogoPack(self.top, origen, self.base)
        except (OSError, ValueError) as e:
            messagebox.showerror(tx("vn.pack_incompatible"), str(e), parent=self.top)

    def _actualizar_pack(self):
        origen = filedialog.askopenfilename(parent=self.top, title=tx("vn.elegir_pack_beta2"),
                                            filetypes=[(tx("vn.tipo_pack"), "*.bin"), (tx("g.todos_archivos"), "*")])
        if not origen:
            return
        nombre, extension = os.path.splitext(os.path.basename(origen))
        destino = filedialog.asksaveasfilename(parent=self.top, title=tx("vn.guardar_final"),
                                               initialfile=nombre + "_nextor3_final" + (extension or ".bin"),
                                               defaultextension=".bin",
                                               filetypes=[(tx("vn.tipo_pack"), "*.bin"), (tx("g.todos_archivos"), "*")])
        if not destino:
            return
        try:
            with open(origen, "rb") as archivo:
                pack = archivo.read()
            with open(self.base, "rb") as archivo:
                base = archivo.read()
            actualizado = nextor_bios.actualizar_pack_bios(pack, base)
            with open(destino, "wb") as archivo:
                archivo.write(actualizado)
        except (OSError, ValueError) as e:
            messagebox.showerror(tx("vn.err_actualizar"), str(e), parent=self.top)
            return
        messagebox.showinfo(tx("vn.pack_actualizado"), tx("vn.pack_actualizado_texto", destino), parent=self.top)

    @staticmethod
    def _hexadecimal(texto, nombre):
        texto = texto.strip().lower().removesuffix("h")
        if not texto:
            return None
        try:
            return int(texto, 16)
        except ValueError as e:
            raise ValueError(tx("vn.hex_invalido", nombre)) from e

    def _crear(self):
        driver = self.rutas["driver"].get()
        if not driver:
            messagebox.showwarning(tx("vn.crear_titulo"), tx("vn.falta_driver"), parent=self.top)
            return
        try:
            def leer(ruta):
                if not ruta:
                    return None
                with open(ruta, "rb") as archivo:
                    return archivo.read()
            rom = nextor_bios.crear_rom(
                leer(self.base), leer(driver), leer(self.rutas["mapper"].get()), leer(self.rutas["extra"].get()),
                self._hexadecimal(self.direccion.get(), tx("vn.hex_mapper")),
                self._hexadecimal(self.teclas.get(), tx("vn.hex_teclas")))
        except (OSError, ValueError) as e:
            messagebox.showerror(tx("vn.err_crear"), str(e), parent=self.top)
            return
        ruta = filedialog.asksaveasfilename(parent=self.top, title=tx("vn.guardar_rom"),
                                            initialfile="Nextor-3.0.0.ROM", defaultextension=".ROM",
                                            filetypes=[(tx("vn.tipo_rom_nextor"), "*.rom"),
                                                       (tx("g.todos_archivos"), "*")])
        if not ruta:
            return
        try:
            with open(ruta, "wb") as archivo:
                archivo.write(rom)
        except OSError as e:
            messagebox.showerror(tx("vn.err_guardar_rom"), str(e), parent=self.top)
            return
        messagebox.showinfo(tx("vn.rom_creada"), tx("vn.rom_creada_texto", ruta, len(rom) // 1024,
                                                    len(rom) // nextor_bios.BANK_SIZE), parent=self.top)
        self.top.destroy()


def abrir(padre):
    Dialogo(padre)
