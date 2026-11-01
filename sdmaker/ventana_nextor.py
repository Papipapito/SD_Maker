"""Ventana del creador de ROM Nextor 3."""
import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from . import contenido, nextor_bios


class Dialogo:
    def __init__(self, padre):
        self.top = tk.Toplevel(padre)
        self.top.title("Crear ROM Nextor 3")
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
        ttk.Label(f, text="Creador de ROM Nextor 3.0", font=("Segoe UI", 14, "bold")).grid(
            row=0, column=0, columnspan=3, sticky="w")
        ttk.Label(f, text="Combina el kernel base oficial incluido con el driver Nextor 3 de tu lector SD. "
                  "Los drivers de Nextor 2 no son compatibles.", wraplength=620, justify="left").grid(
            row=1, column=0, columnspan=3, sticky="w", pady=(4, 14))

        pack = ttk.LabelFrame(f, text="Pack BIOS de MSXnano o MSXimus")
        pack.grid(row=2, column=0, columnspan=3, sticky="ew", pady=(0, 14))
        ttk.Label(pack, text="Actualiza un pack con Nextor 3 beta 2 al kernel 3.0 final, conservando las demás ROM "
                  "y el driver de su lector SD.", wraplength=480, justify="left").pack(side="left", padx=10, pady=9)
        ttk.Button(pack, text="Actualizar pack…", command=self._actualizar_pack).pack(side="right", padx=10, pady=9)

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
