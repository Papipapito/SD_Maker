"""Ventana del creador de ROM Nextor 3."""
import hashlib
import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from . import contenido, nextor_bios
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
        self.top.title("Personalizar pack BIOS MSXnano / MSXimus")
        self.top.transient(padre)
        self.top.resizable(False, False)
        self._construir()
        self.top.grab_set()
        self.top.wait_window()

    def _construir(self):
        f = ttk.Frame(self.top, padding=14)
        f.pack(fill="both", expand=True)
        ttk.Label(f, text="Bloques del pack BIOS", font=("Segoe UI", 14, "bold")).grid(
            row=0, column=0, columnspan=5, sticky="w")
        ttk.Label(f, text=os.path.basename(self.ruta), foreground="#666666").grid(
            row=1, column=0, columnspan=5, sticky="w", pady=(2, 8))
        ttk.Label(f, text="Cada bloque tiene una posición y tamaño fijos. File-Hunter sólo permite resultados del "
                  "tamaño exacto; eso no garantiza que sean BIOS compatibles con este core.", wraplength=760,
                  justify="left").grid(row=2, column=0, columnspan=5, sticky="w", pady=(0, 10))
        ttk.Label(f, text="Bloque", font=("Segoe UI", 9, "bold")).grid(row=3, column=0, sticky="w")
        ttk.Label(f, text="Posición", font=("Segoe UI", 9, "bold")).grid(row=3, column=1, sticky="w")
        ttk.Label(f, text="Estado", font=("Segoe UI", 9, "bold")).grid(row=3, column=2, sticky="w")
        for fila, (clave, nombre, offset, tamano, editable, datos) in enumerate(
                nextor_bios.bloques_pack(self.original), 4):
            ttk.Label(f, text=nombre).grid(row=fila, column=0, sticky="w", pady=3)
            ttk.Label(f, text="%05Xh · %d KB" % (offset, tamano // 1024)).grid(
                row=fila, column=1, sticky="w", padx=(12, 16))
            estado = ttk.Label(f, text=self._hash(datos), width=19)
            estado.grid(row=fila, column=2, sticky="w")
            self.estado[clave] = estado
            if clave == "nextor":
                ttk.Button(f, text="Nextor 3 final", command=self._nextor_final).grid(
                    row=fila, column=3, columnspan=2, sticky="ew", padx=(8, 0))
            elif editable:
                ttk.Button(f, text="Archivo…", command=lambda c=clave, t=tamano: self._archivo(c, t)).grid(
                    row=fila, column=3, padx=(8, 0))
                ttk.Button(f, text="File-Hunter…", command=lambda c=clave, n=nombre, t=tamano:
                           self._filehunter(c, n, t)).grid(row=fila, column=4, padx=(6, 0))
            else:
                ttk.Label(f, text="protegido", foreground="#777777").grid(
                    row=fila, column=3, columnspan=2, sticky="w", padx=(8, 0))
        aviso_fila = 4 + len(nextor_bios.PACK_BLOCKS)
        ttk.Label(f, text="Importante: el bloque MSX-MUSIC comparte sus 16 KB con la primera página del menú. "
                  "Sustituirlo por una ROM normal elimina el menú. La reserva de 74000h no está conectada como "
                  "slot y no puede alojar utilidades.", wraplength=760, justify="left", foreground="#9a5400").grid(
            row=aviso_fila, column=0, columnspan=5, sticky="w", pady=(10, 4))
        pie = ttk.Frame(f)
        pie.grid(row=aviso_fila + 1, column=0, columnspan=5, sticky="ew", pady=(12, 0))
        ttk.Button(pie, text="Cancelar", command=self.top.destroy).pack(side="right")
        ttk.Button(pie, text="Guardar pack personalizado…", command=self._guardar).pack(
            side="right", padx=(0, 8))
        ttk.Button(pie, text="Restaurar todos", command=self._restaurar).pack(side="left")

    @staticmethod
    def _hash(datos):
        return hashlib.sha256(datos).hexdigest()[:12]

    def _poner(self, clave, ruta, tamano):
        try:
            with open(ruta, "rb") as f:
                datos = f.read()
        except OSError as e:
            messagebox.showerror("No se puede leer", str(e), parent=self.top)
            return
        if len(datos) != tamano:
            messagebox.showerror("Tamaño incompatible", "%s mide %d bytes; este bloque necesita exactamente %d." %
                                 (os.path.basename(ruta), len(datos), tamano), parent=self.top)
            return
        if clave == "music_menu" and not messagebox.askyesno(
                "El menú dejará de funcionar", "Este bloque también contiene la primera página del menú interno. "
                "Una ROM MSX-MUSIC normal eliminará ese menú.\n\n¿Sustituirlo de todos modos?", parent=self.top):
            return
        self.reemplazos[clave] = datos
        self.estado[clave]["text"] = self._hash(datos) + "  modificado"

    def _archivo(self, clave, tamano):
        ruta = filedialog.askopenfilename(parent=self.top, title="Elegir ROM de %d KB" % (tamano // 1024),
                                          filetypes=[("ROM o binario", "*.rom *.bin"), ("Todos", "*")])
        if ruta:
            self._poner(clave, ruta, tamano)

    def _filehunter(self, clave, nombre, tamano):
        d = DialogoFileHunter(self.top, tamano_kb=tamano // 1024, contexto="el bloque «%s»" % nombre)
        if d.resultado:
            self._poner(clave, d.resultado, tamano)

    def _nextor_final(self):
        try:
            with open(self.base, "rb") as f:
                base = f.read()
            self.pack_base = nextor_bios.actualizar_pack_bios(self.pack_base, base)
        except (OSError, ValueError) as e:
            messagebox.showerror("No se puede actualizar Nextor", str(e), parent=self.top)
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
        destino = filedialog.asksaveasfilename(parent=self.top, title="Guardar pack BIOS personalizado",
                                               initialfile=nombre + "_personalizado" + (ext or ".bin"),
                                               defaultextension=".bin",
                                               filetypes=[("Pack BIOS", "*.bin"), ("Todos", "*")])
        if not destino:
            return
        try:
            datos = nextor_bios.personalizar_pack(self.pack_base, self.reemplazos)
            with open(destino, "wb") as f:
                f.write(datos)
        except (OSError, ValueError) as e:
            messagebox.showerror("No se puede guardar", str(e), parent=self.top)
            return
        messagebox.showinfo("Pack creado", "%s\n\nSe han conservado todos los bloques no modificados y la "
                            "configuración de 6 bytes, si la tenía." % destino, parent=self.top)
        self.top.destroy()


class Dialogo:
    def __init__(self, padre):
        self.top = tk.Toplevel(padre)
        self.top.title("Crear o personalizar pack BIOS")
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
        ttk.Label(f, text="Pack BIOS y Nextor 3.0", font=("Segoe UI", 14, "bold")).grid(
            row=0, column=0, columnspan=3, sticky="w")
        ttk.Label(f, text="Combina el kernel base oficial incluido con el driver Nextor 3 de tu lector SD. "
                  "Los drivers de Nextor 2 no son compatibles.", wraplength=620, justify="left").grid(
            row=1, column=0, columnspan=3, sticky="w", pady=(4, 14))

        pack = ttk.LabelFrame(f, text="Pack BIOS de MSXnano o MSXimus")
        pack.grid(row=2, column=0, columnspan=3, sticky="ew", pady=(0, 14))
        ttk.Label(pack, text="Edita por separado BIOS, SubROM, kanji, red y logo, o actualiza únicamente Nextor. "
                  "Los bloques del menú quedan identificados y protegidos.", wraplength=430,
                  justify="left").pack(side="left", padx=10, pady=9)
        botones_pack = ttk.Frame(pack)
        botones_pack.pack(side="right", padx=10, pady=9)
        ttk.Button(botones_pack, text="Personalizar bloques…", command=self._personalizar_pack).pack(anchor="e")
        ttk.Button(botones_pack, text="Sólo actualizar Nextor…", command=self._actualizar_pack).pack(
            anchor="e", pady=(5, 0))

        base = os.path.join(contenido.carpeta_sd(), "nextor-3.0.0", "Nextor-3.0.0.base.dat")
        ttk.Separator(f).grid(row=3, column=0, columnspan=3, sticky="ew", pady=(0, 10))
        ttk.Label(f, text="ROM Nextor avanzada", font=("Segoe UI", 11, "bold")).grid(
            row=4, column=0, columnspan=3, sticky="w", pady=(0, 5))
        ttk.Label(f, text="Kernel base").grid(row=5, column=0, sticky="w", pady=4)
        ttk.Label(f, text=base, foreground="#666666", wraplength=490).grid(row=5, column=1, columnspan=2, sticky="w")
        self.base = base

        filas = (("driver", "Driver Nextor 3", True), ("mapper", "Código de mapper", False),
                 ("extra", "Código/datos extra", False))
        for fila, (clave, texto, obligatorio) in enumerate(filas, 6):
            ttk.Label(f, text=texto + (" *" if obligatorio else " (opcional)")).grid(row=fila, column=0, sticky="w",
                                                                                       pady=4)
            ttk.Entry(f, textvariable=self.rutas[clave], width=56, state="readonly").grid(
                row=fila, column=1, sticky="ew", padx=(10, 8), pady=4)
            ttk.Button(f, text="Elegir…", command=lambda c=clave: self._elegir(c)).grid(row=fila, column=2, pady=4)

        ttk.Label(f, text="Mapper de 8 KB (opcional)").grid(row=9, column=0, sticky="w", pady=4)
        ttk.Entry(f, textvariable=self.direccion, width=12).grid(row=9, column=1, sticky="w", padx=(10, 0), pady=4)
        ttk.Label(f, text="Dirección hexadecimal 4000–7FFF; normalmente se deja vacío.", foreground="#666666").grid(
            row=9, column=1, columnspan=2, sticky="e")
        ttk.Label(f, text="Invertir teclas (opcional)").grid(row=10, column=0, sticky="w", pady=4)
        ttk.Entry(f, textvariable=self.teclas, width=12).grid(row=10, column=1, sticky="w", padx=(10, 0), pady=4)
        ttk.Label(f, text="Valor hexadecimal de 16 bits, por ejemplo 1002.", foreground="#666666").grid(
            row=10, column=1, columnspan=2, sticky="e")

        ttk.Label(f, text="* El driver debe llevar la firma NEXTORv3_DRIVER. La ROM generada no se instala ni se "
                  "flashea automáticamente.", wraplength=620, foreground="#7a4c00", justify="left").grid(
            row=11, column=0, columnspan=3, sticky="w", pady=(12, 6))
        pie = ttk.Frame(f)
        pie.grid(row=12, column=0, columnspan=3, sticky="e", pady=(10, 0))
        ttk.Button(pie, text="Cancelar", command=self.top.destroy).pack(side="right")
        ttk.Button(pie, text="Crear ROM…", command=self._crear).pack(side="right", padx=(0, 8))

    def _elegir(self, clave):
        tipos = (("Driver o binario", "*.bin *.drv *.rom"), ("Todos los archivos", "*"))
        ruta = filedialog.askopenfilename(parent=self.top, title="Elegir " + clave, filetypes=tipos)
        if ruta:
            self.rutas[clave].set(ruta)

    def _personalizar_pack(self):
        origen = filedialog.askopenfilename(parent=self.top, title="Elegir pack BIOS de MSXnano o MSXimus",
                                            filetypes=[("Pack BIOS", "*.bin"), ("Todos los archivos", "*")])
        if not origen:
            return
        try:
            DialogoPack(self.top, origen, self.base)
        except (OSError, ValueError) as e:
            messagebox.showerror("Pack incompatible", str(e), parent=self.top)

    def _actualizar_pack(self):
        origen = filedialog.askopenfilename(parent=self.top, title="Elegir pack BIOS con Nextor 3 beta 2",
                                            filetypes=[("Pack BIOS", "*.bin"), ("Todos los archivos", "*")])
        if not origen:
            return
        nombre, extension = os.path.splitext(os.path.basename(origen))
        destino = filedialog.asksaveasfilename(parent=self.top, title="Guardar pack con Nextor 3.0 final",
                                               initialfile=nombre + "_nextor3_final" + (extension or ".bin"),
                                               defaultextension=".bin",
                                               filetypes=[("Pack BIOS", "*.bin"), ("Todos los archivos", "*")])
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
            messagebox.showerror("No se puede actualizar el pack", str(e), parent=self.top)
            return
        messagebox.showinfo("Pack actualizado", "%s\n\nSe han conservado todas las ROM y la configuración; sólo "
                            "se ha sustituido el bloque Nextor por la versión 3.0 final." % destino, parent=self.top)

    @staticmethod
    def _hexadecimal(texto, nombre):
        texto = texto.strip().lower().removesuffix("h")
        if not texto:
            return None
        try:
            return int(texto, 16)
        except ValueError as e:
            raise ValueError("%s no es un número hexadecimal válido" % nombre) from e

    def _crear(self):
        driver = self.rutas["driver"].get()
        if not driver:
            messagebox.showwarning("Crear ROM Nextor 3", "Elige el driver Nextor 3 de tu hardware.", parent=self.top)
            return
        try:
            def leer(ruta):
                if not ruta:
                    return None
                with open(ruta, "rb") as archivo:
                    return archivo.read()
            rom = nextor_bios.crear_rom(
                leer(self.base), leer(driver), leer(self.rutas["mapper"].get()), leer(self.rutas["extra"].get()),
                self._hexadecimal(self.direccion.get(), "La dirección del mapper"),
                self._hexadecimal(self.teclas.get(), "El inversor de teclas"))
        except (OSError, ValueError) as e:
            messagebox.showerror("No se puede crear la ROM", str(e), parent=self.top)
            return
        ruta = filedialog.asksaveasfilename(parent=self.top, title="Guardar ROM Nextor 3",
                                            initialfile="Nextor-3.0.0.ROM", defaultextension=".ROM",
                                            filetypes=[("ROM de Nextor", "*.rom"), ("Todos los archivos", "*")])
        if not ruta:
            return
        try:
            with open(ruta, "wb") as archivo:
                archivo.write(rom)
        except OSError as e:
            messagebox.showerror("No se puede guardar la ROM", str(e), parent=self.top)
            return
        messagebox.showinfo("ROM creada", "%s\n\n%d KB, %d bancos de 16 KB." %
                            (ruta, len(rom) // 1024, len(rom) // nextor_bios.BANK_SIZE), parent=self.top)
        self.top.destroy()


def abrir(padre):
    Dialogo(padre)
