"""Dispositivos de salida: imágenes y tarjetas físicas de Windows o macOS.

En Windows se usa ``\\\\.\\PhysicalDriveN``. En macOS se enumeran medios físicos externos con ``diskutil`` y se
escribe el dispositivo de caracteres ``/dev/rdiskN`` después de desmontarlo. En los dos sistemas se excluye el disco
del sistema, se aceptan por defecto sólo lectores SD/MMC y memorias USB extraíbles y se vuelve a validar el dispositivo
justo antes de abrirlo: esta es la barrera de seguridad de la operación que borra la tarjeta entera.
"""
import os
import plistlib
import re
import stat
import struct
import subprocess
import sys
import time

SECTOR = 512


class Imagen:
    """Fichero de imagen. Si no existe se crea del tamano pedido (disperso en ext4/NTFS: no ocupa lo no escrito)."""

    def __init__(self, ruta, sectores=None):
        self.ruta = ruta
        if sectores is not None:
            with open(ruta, "wb") as f:
                if sys.platform == "win32":
                    _dispersa(f)
                f.truncate(sectores * SECTOR)
        self.f = open(ruta, "r+b")
        self.f.seek(0, 2)
        self.sectores = self.f.tell() // SECTOR
        self.nombre = os.path.basename(ruta)

    def escribir(self, lba, datos):
        assert len(datos) % SECTOR == 0, "escritura no alineada"
        self.f.seek(lba * SECTOR)
        self.f.write(datos)

    def leer(self, lba, n=1):
        self.f.seek(lba * SECTOR)
        return self.f.read(n * SECTOR)

    def cerrar(self):
        self.f.close()


if sys.platform == "win32":
    import ctypes
    from ctypes import wintypes as wt

    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.CreateFileW.argtypes = [wt.LPCWSTR, wt.DWORD, wt.DWORD, wt.LPVOID, wt.DWORD, wt.DWORD, wt.HANDLE]
    k32.CreateFileW.restype = wt.HANDLE
    k32.DeviceIoControl.argtypes = [wt.HANDLE, wt.DWORD, wt.LPVOID, wt.DWORD, wt.LPVOID, wt.DWORD,
                                    ctypes.POINTER(wt.DWORD), wt.LPVOID]
    k32.DeviceIoControl.restype = wt.BOOL
    k32.SetFilePointerEx.argtypes = [wt.HANDLE, ctypes.c_longlong, ctypes.POINTER(ctypes.c_longlong), wt.DWORD]
    k32.SetFilePointerEx.restype = wt.BOOL
    k32.WriteFile.argtypes = [wt.HANDLE, wt.LPVOID, wt.DWORD, ctypes.POINTER(wt.DWORD), wt.LPVOID]
    k32.WriteFile.restype = wt.BOOL
    k32.ReadFile.argtypes = [wt.HANDLE, wt.LPVOID, wt.DWORD, ctypes.POINTER(wt.DWORD), wt.LPVOID]
    k32.ReadFile.restype = wt.BOOL
    k32.CloseHandle.argtypes = [wt.HANDLE]
    k32.FlushFileBuffers.argtypes = [wt.HANDLE]
    k32.FindFirstVolumeW.argtypes = [wt.LPWSTR, wt.DWORD]
    k32.FindFirstVolumeW.restype = wt.HANDLE
    k32.FindNextVolumeW.argtypes = [wt.HANDLE, wt.LPWSTR, wt.DWORD]
    k32.FindVolumeClose.argtypes = [wt.HANDLE]
    k32.GetVolumePathNamesForVolumeNameW.argtypes = [wt.LPCWSTR, wt.LPWSTR, wt.DWORD, ctypes.POINTER(wt.DWORD)]

    INVALIDO = wt.HANDLE(-1).value
    GENERIC_READ, GENERIC_WRITE = 0x80000000, 0x40000000
    SHARE_RW, OPEN_EXISTING = 3, 3
    IOCTL_DISK_GET_LENGTH_INFO = 0x0007405C       # necesita acceso de lectura (administrador)
    IOCTL_DISK_GET_DRIVE_GEOMETRY_EX = 0x000700A0  # sin acceso: sirve para listar sin ser administrador
    IOCTL_STORAGE_QUERY_PROPERTY = 0x002D1400
    IOCTL_STORAGE_GET_DEVICE_NUMBER = 0x002D1080
    IOCTL_DISK_UPDATE_PROPERTIES = 0x00070140
    FSCTL_LOCK_VOLUME, FSCTL_DISMOUNT_VOLUME = 0x00090018, 0x00090020
    BUS = {7: "USB", 12: "SD", 13: "MMC", 11: "SATA", 17: "NVMe", 3: "ATA", 1: "SCSI", 14: "Virtual"}

    def _abrir(ruta, acceso):
        h = k32.CreateFileW(ruta, acceso, SHARE_RW, None, OPEN_EXISTING, 0, None)
        if h == INVALIDO or h is None:
            raise OSError(ctypes.get_last_error(), "no se puede abrir " + ruta)
        return h

    def _ioctl(h, codigo, entrada=None, tam_salida=0):
        salida = ctypes.create_string_buffer(tam_salida) if tam_salida else None
        n = wt.DWORD(0)
        ent = ctypes.create_string_buffer(entrada) if entrada else None
        ok = k32.DeviceIoControl(h, codigo, ent, len(entrada) if entrada else 0, salida, tam_salida, ctypes.byref(n), None)
        if not ok:
            raise OSError(ctypes.get_last_error(), "DeviceIoControl %08X" % codigo)
        return salida.raw[:n.value] if salida else b""

    def _numero_disco(ruta_volumen):
        """Numero de disco fisico de un volumen (\\\\.\\E: o \\\\?\\Volume{...}) o None."""
        try:
            h = _abrir(ruta_volumen, 0)
        except OSError:
            return None
        try:
            _, numero, _ = struct.unpack("<III", _ioctl(h, IOCTL_STORAGE_GET_DEVICE_NUMBER, None, 12))
            return numero
        except OSError:
            return None
        finally:
            k32.CloseHandle(h)

    def _volumenes():
        """[(ruta \\\\?\\Volume{...} sin barra final, [letras], numero de disco)]"""
        out = []
        buf = ctypes.create_unicode_buffer(1024)
        h = k32.FindFirstVolumeW(buf, 1024)
        if h == INVALIDO:
            return out
        try:
            while True:
                vol = buf.value
                letras = []
                nombres = ctypes.create_unicode_buffer(1024)
                n = wt.DWORD(0)
                if k32.GetVolumePathNamesForVolumeNameW(vol, nombres, 1024, ctypes.byref(n)):
                    letras = [p for p in nombres[:n.value].split("\x00") if len(p) == 3 and p[1] == ":"]
                out.append((vol.rstrip("\\"), letras, _numero_disco(vol.rstrip("\\"))))
                if not k32.FindNextVolumeW(h, buf, 1024):
                    break
        finally:
            k32.FindVolumeClose(h)
        return out

    def disco_del_sistema():
        return _numero_disco("\\\\.\\" + os.environ.get("SystemDrive", "C:"))

    def listar_tarjetas(incluir_usb_fijos=False):
        """[{numero, sectores, bytes, modelo, bus, extraible, letras}] de las tarjetas a las que se puede escribir."""
        sistema = disco_del_sistema()
        vols = _volumenes()
        out = []
        for i in range(32):
            try:
                h = _abrir("\\\\.\\PhysicalDrive%d" % i, 0)
            except OSError:
                continue
            try:
                geo = _ioctl(h, IOCTL_DISK_GET_DRIVE_GEOMETRY_EX, None, 256)
                bps = struct.unpack_from("<I", geo, 20)[0]
                longitud = struct.unpack_from("<q", geo, 24)[0]
                d = _ioctl(h, IOCTL_STORAGE_QUERY_PROPERTY, struct.pack("<II4x", 0, 0), 1024)
            except OSError:
                continue
            finally:
                k32.CloseHandle(h)
            extraible = d[10] != 0
            vend_o, prod_o = struct.unpack_from("<II", d, 12)
            bus = struct.unpack_from("<I", d, 28)[0]

            def cad(o):
                return d[o:d.index(b"\x00", o)].decode("ascii", "replace").strip() if o and o < len(d) else ""
            modelo = (cad(vend_o) + " " + cad(prod_o)).strip() or "sin nombre"
            valido = bus in (12, 13) or (bus == 7 and (extraible or incluir_usb_fijos))
            if i == sistema or not valido or longitud <= 0 or bps != SECTOR:
                continue
            letras = sorted(l for v, ls, n in vols if n == i for l in ls)
            out.append({"numero": i, "sectores": longitud // SECTOR, "bytes": longitud, "modelo": modelo,
                        "bus": BUS.get(bus, str(bus)), "extraible": extraible, "letras": letras})
        return out

    def es_admin():
        try:
            return bool(ctypes.windll.shell32.IsUserAnAdmin())
        except Exception:
            return False

    def _dispersa(f):
        """Fichero disperso en NTFS: una imagen de 32 GB solo ocupa lo escrito."""
        import msvcrt
        try:
            _ioctl(wt.HANDLE(msvcrt.get_osfhandle(f.fileno())), 0x000900C4)   # FSCTL_SET_SPARSE
        except OSError:
            pass

    class DiscoLectura:
        """Solo lectura (para ver la tabla de particiones actual), sin bloquear nada."""

        def __init__(self, numero):
            self.h = _abrir("\\\\.\\PhysicalDrive%d" % numero, GENERIC_READ)

        def leer(self, lba, n=1):
            if not k32.SetFilePointerEx(self.h, lba * SECTOR, None, 0):
                raise OSError(ctypes.get_last_error(), "no se puede ir al sector %d" % lba)
            buf = ctypes.create_string_buffer(n * SECTOR)
            m = wt.DWORD(0)
            if not k32.ReadFile(self.h, buf, n * SECTOR, ctypes.byref(m), None):
                raise OSError(ctypes.get_last_error(), "error de lectura en el sector %d" % lba)
            return buf.raw[:m.value]

        def cerrar(self):
            k32.CloseHandle(self.h)

    class DiscoWindows:
        """La tarjeta entera. abrir() bloquea y desmonta sus volumenes; cerrar() hace que Windows relea la tabla."""

        def __init__(self, numero):
            if numero == disco_del_sistema():
                raise PermissionError("ese es el disco de Windows")
            self.numero = numero
            self.nombre = "Disco %d" % numero
            self.bloqueos = []
            for vol, letras, n in _volumenes():
                if n != numero:
                    continue
                hv = _abrir(vol, GENERIC_READ | GENERIC_WRITE)
                for intento in range(10):      # el Explorador suele soltarla en un momento
                    try:
                        _ioctl(hv, FSCTL_LOCK_VOLUME)
                        break
                    except OSError as e:
                        if intento == 9:
                            k32.CloseHandle(hv)
                            self._soltar()
                            raise OSError(e.errno, "la unidad %s esta en uso: cierra lo que la tenga abierta"
                                          % (letras[0] if letras else vol))
                        time.sleep(0.5)
                _ioctl(hv, FSCTL_DISMOUNT_VOLUME)
                self.bloqueos.append(hv)
            self.h = _abrir("\\\\.\\PhysicalDrive%d" % numero, GENERIC_READ | GENERIC_WRITE)
            self.sectores = struct.unpack("<q", _ioctl(self.h, IOCTL_DISK_GET_LENGTH_INFO, None, 8))[0] // SECTOR

        def _mover(self, lba):
            if not k32.SetFilePointerEx(self.h, lba * SECTOR, None, 0):
                raise OSError(ctypes.get_last_error(), "no se puede ir al sector %d" % lba)

        def escribir(self, lba, datos):
            assert len(datos) % SECTOR == 0
            self._mover(lba)
            buf = ctypes.create_string_buffer(bytes(datos), len(datos))
            n = wt.DWORD(0)
            if not k32.WriteFile(self.h, buf, len(datos), ctypes.byref(n), None) or n.value != len(datos):
                raise OSError(ctypes.get_last_error(), "error de escritura en el sector %d" % lba)

        def leer(self, lba, n=1):
            self._mover(lba)
            buf = ctypes.create_string_buffer(n * SECTOR)
            m = wt.DWORD(0)
            if not k32.ReadFile(self.h, buf, n * SECTOR, ctypes.byref(m), None):
                raise OSError(ctypes.get_last_error(), "error de lectura en el sector %d" % lba)
            return buf.raw[:m.value]

        def _soltar(self):
            for hv in self.bloqueos:
                k32.CloseHandle(hv)
            self.bloqueos = []

        def cerrar(self):
            k32.FlushFileBuffers(self.h)
            try:
                _ioctl(self.h, IOCTL_DISK_UPDATE_PROPERTIES)
            except OSError:
                pass
            k32.CloseHandle(self.h)
            self._soltar()

    Disco = DiscoWindows

elif sys.platform == "darwin":
    DISKUTIL = "/usr/sbin/diskutil"

    def _diskutil_plist(*args):
        p = subprocess.run([DISKUTIL, *args], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
        if p.returncode:
            detalle = p.stderr.decode("utf-8", "replace").strip() or p.stdout.decode("utf-8", "replace").strip()
            raise OSError("diskutil %s: %s" % (" ".join(args), detalle or "error %d" % p.returncode))
        try:
            return plistlib.loads(p.stdout)
        except Exception as e:
            raise OSError("diskutil %s no devolvio una lista valida: %s" % (" ".join(args), e))

    def _diskutil(*args):
        p = subprocess.run([DISKUTIL, *args], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
        texto = (p.stderr or p.stdout).strip()
        if p.returncode:
            raise OSError("diskutil %s: %s" % (" ".join(args), texto or "error %d" % p.returncode))
        return (p.stdout or "").strip()

    def _identificadores(nodo):
        """Identificadores BSD mencionados en un plist (disk3s1 -> disk3)."""
        out = set()
        if isinstance(nodo, dict):
            for v in nodo.values():
                out.update(_identificadores(v))
        elif isinstance(nodo, (list, tuple)):
            for v in nodo:
                out.update(_identificadores(v))
        elif isinstance(nodo, str):
            m = re.fullmatch(r"(?:/dev/)?(disk\d+)(?:s\d+)*", nodo)
            if m:
                out.add(m.group(1))
        return out

    def _discos_sistema():
        """Todos los discos, incluidos Physical Stores de APFS, de los que depende el volumen raíz."""
        return _identificadores(_diskutil_plist("info", "-plist", "/"))

    def disco_del_sistema():
        discos = sorted(_discos_sistema(), key=lambda x: int(x[4:]))
        return int(discos[0][4:]) if discos else None

    def _particiones(entrada):
        out = []

        def recorrer(nodo):
            if isinstance(nodo, dict):
                ident = nodo.get("DeviceIdentifier")
                if ident and re.fullmatch(r"disk\d+s\d+(?:s\d+)?", ident):
                    out.append({"identificador": ident, "bytes": int(nodo.get("Size") or 0),
                                "tipo": nodo.get("Content") or nodo.get("FilesystemType") or "desconocido",
                                "nombre": nodo.get("VolumeName") or "", "montaje": nodo.get("MountPoint") or ""})
                for v in nodo.values():
                    recorrer(v)
            elif isinstance(nodo, list):
                for v in nodo:
                    recorrer(v)

        recorrer(entrada.get("Partitions", []))
        # Un volumen APFS puede aparecer varias veces en el árbol del plist.
        unicas = {}
        for p in out:
            unicas[p["identificador"]] = p
        return [unicas[k] for k in sorted(unicas)]

    def _entrada_por_disco(lista, identificador):
        for entrada in lista.get("AllDisksAndPartitions", []):
            if entrada.get("DeviceIdentifier") == identificador:
                return entrada
        return {}

    def _tarjeta_desde_info(identificador, info, entrada, incluir_usb_fijos=False):
        if not re.fullmatch(r"disk\d+", identificador) or not info.get("WholeDisk"):
            return None
        if info.get("Internal") or info.get("OSInternalMedia"):
            return None
        if not info.get("WritableMedia", info.get("Writable", False)):
            return None
        if int(info.get("DeviceBlockSize") or 0) != SECTOR:
            return None
        bus = str(info.get("BusProtocol") or "externo")
        extraible = bool(info.get("RemovableMedia") or info.get("Removable") or info.get("Ejectable"))
        if not extraible and not (incluir_usb_fijos and bus.upper() == "USB"):
            return None
        nbytes = int(info.get("TotalSize") or info.get("Size") or 0)
        if nbytes <= 0 or nbytes % SECTOR:
            return None
        partes = _particiones(entrada)
        montajes = [p["montaje"] or p["nombre"] for p in partes if p["montaje"] or p["nombre"]]
        modelo = (info.get("MediaName") or info.get("IORegistryEntryName") or "sin nombre").strip()
        identidad = "|".join(str(info.get(k) or "") for k in
                              ("DeviceTreePath", "IORegistryEntryName", "MediaUUID", "DiskUUID"))
        return {"numero": int(identificador[4:]), "identificador": identificador, "sectores": nbytes // SECTOR,
                "bytes": nbytes, "modelo": modelo, "bus": bus, "extraible": extraible, "letras": montajes,
                "particiones": partes, "identidad": identidad}

    def listar_tarjetas(incluir_usb_fijos=False):
        """Tarjetas físicas externas y extraíbles; nunca un disco del que dependa el volumen raíz."""
        lista = _diskutil_plist("list", "-plist", "external", "physical")
        sistema = _discos_sistema()
        out = []
        for identificador in lista.get("WholeDisks", []):
            if identificador in sistema:
                continue
            info = _diskutil_plist("info", "-plist", "/dev/" + identificador)
            t = _tarjeta_desde_info(identificador, info, _entrada_por_disco(lista, identificador),
                                    incluir_usb_fijos)
            if t is not None:
                out.append(t)
        return out

    def es_admin():
        return os.geteuid() == 0

    def _misma_tarjeta(actual, esperada):
        if not esperada:
            return True
        if actual["bytes"] != int(esperada.get("bytes") or 0):
            return False
        identidad = esperada.get("identidad")
        if identidad and actual.get("identidad") != identidad:
            return False
        modelo = esperada.get("modelo")
        return not modelo or actual.get("modelo") == modelo

    def _buscar_tarjeta(numero):
        for t in listar_tarjetas():
            if t["numero"] == numero:
                return t
        return None

    class DiscoLectura:
        """Lectura directa para la línea de órdenes cuando ya se ejecuta como root."""

        def __init__(self, numero):
            self.f = os.open("/dev/rdisk%d" % numero, os.O_RDONLY)

        def leer(self, lba, n=1):
            return os.pread(self.f, n * SECTOR, lba * SECTOR)

        def cerrar(self):
            os.close(self.f)

    class DiscoMacOS:
        """Tarjeta completa: valida, desmonta, escribe por rdisk y vuelve a montar al cerrar."""

        def __init__(self, numero, esperada=None):
            self.numero = int(numero)
            self.identificador = "disk%d" % self.numero
            self.nombre = "/dev/" + self.identificador
            self.f = None
            self.aviso_cierre = None
            if self.identificador in _discos_sistema():
                raise PermissionError("ese disco contiene el sistema de macOS")
            actual = _buscar_tarjeta(self.numero)
            if actual is None:
                raise PermissionError("%s ya no es una tarjeta externa y extraible valida" % self.nombre)
            if not _misma_tarjeta(actual, esperada):
                raise PermissionError("la tarjeta de %s ha cambiado desde que se eligio; pulsa Actualizar" % self.nombre)
            _diskutil("unmountDisk", self.nombre)
            try:
                # Entre la confirmación y este punto la tarjeta puede haberse extraído o sustituido.
                actual = _buscar_tarjeta(self.numero)
                if actual is None or not _misma_tarjeta(actual, esperada or actual):
                    raise PermissionError("la tarjeta de %s ha cambiado durante el desmontaje" % self.nombre)
                ruta = "/dev/r" + self.identificador
                modo = os.stat(ruta).st_mode
                if not stat.S_ISCHR(modo):
                    raise PermissionError("%s no es un dispositivo de caracteres" % ruta)
                self.f = os.open(ruta, os.O_RDWR)
                self.sectores = actual["sectores"]
            except Exception:
                try:
                    _diskutil("mountDisk", self.nombre)
                except OSError:
                    pass
                raise

        def escribir(self, lba, datos):
            assert len(datos) % SECTOR == 0, "escritura no alineada"
            if lba < 0 or lba + len(datos) // SECTOR > self.sectores:
                raise OSError("escritura fuera de la tarjeta en el sector %d" % lba)
            vista = memoryview(datos)
            posicion = lba * SECTOR
            while vista:
                n = os.pwrite(self.f, vista, posicion)
                if n <= 0:
                    raise OSError("error de escritura en el sector %d" % lba)
                vista = vista[n:]
                posicion += n

        def leer(self, lba, n=1):
            if lba < 0 or n < 0 or lba + n > self.sectores:
                raise OSError("lectura fuera de la tarjeta en el sector %d" % lba)
            faltan = n * SECTOR
            posicion = lba * SECTOR
            partes = []
            while faltan:
                datos = os.pread(self.f, faltan, posicion)
                if not datos:
                    raise OSError("lectura incompleta en el sector %d" % lba)
                partes.append(datos)
                faltan -= len(datos)
                posicion += len(datos)
            return b"".join(partes)

        def cerrar(self):
            error = None
            if self.f is not None:
                try:
                    os.fsync(self.f)
                except OSError as e:
                    error = e
                finally:
                    os.close(self.f)
                    self.f = None
            try:
                _diskutil("mountDisk", self.nombre)
            except OSError as e:
                self.aviso_cierre = ("La tarjeta esta preparada, pero macOS no ha podido montar sus particiones: %s. "
                                      "Extraela y vuelve a insertarla." % e)
            if error:
                raise error

    Disco = DiscoMacOS

else:
    def listar_tarjetas(incluir_usb_fijos=False):
        return []

    def es_admin():
        return os.geteuid() == 0 if hasattr(os, "geteuid") else False

    def disco_del_sistema():
        return None

    Disco = None


def formato_tamano(nbytes):
    for unidad, div in (("TB", 1 << 40), ("GB", 1 << 30), ("MB", 1 << 20), ("KB", 1 << 10)):
        if nbytes >= div:
            return ("%.2f %s" % (nbytes / div, unidad)).replace(".", ",")
    return "%d B" % nbytes
