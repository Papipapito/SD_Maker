"""Elevación puntual para escribir una tarjeta en macOS.

La ventana sigue ejecutándose con la cuenta del usuario. Sólo se lanza otra copia del ejecutable, mediante el diálogo
estándar de administrador de macOS, para desmontar y abrir ``/dev/rdiskN``. El trabajo y el resultado se intercambian
en ficheros privados de una carpeta temporal; el progreso se escribe como JSON Lines para que la ventana no se quede
sin información mientras se prepara la tarjeta.
"""
import json
import os
import shlex
import subprocess
import sys
import tempfile
import time

from . import contenido, idioma, ocm, particiones, proceso
from . import dispositivos


def datos_trabajo(tarjeta, plan, sistema, grupos, etiqueta, opciones, datos_ocm=None):
    esperado = {k: tarjeta.get(k) for k in ("numero", "bytes", "modelo", "identidad")}
    ps = [{"numero": p.numero, "lba": p.lba, "sectores": p.sectores, "tipo": p.tipo,
           "activa": p.activa, "lba_ebr": p.lba_ebr} for p in plan]
    d_ocm = None
    if datos_ocm:
        d_ocm = {"ruta": datos_ocm["pack"].ruta,
                 "bios": [[nombre, dict(receta)] for nombre, receta in datos_ocm["bios"]]}
    return {"formato": 1, "idioma": idioma.actual(), "tarjeta": esperado, "plan": ps, "sistema": sistema,
            "grupos": sorted(grupos), "etiqueta": etiqueta, "opciones": dict(opciones), "ocm": d_ocm}


def _comando_ayudante(ruta):
    if getattr(sys, "frozen", False):
        return [sys.executable, "--ayudante-macos", ruta]
    principal = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "MSXsdmaker.py"))
    return [sys.executable, principal, "--ayudante-macos", ruta]


def _cadena_applescript(texto):
    return '"' + texto.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _leer_progreso(f, aviso):
    while True:
        linea = f.readline()
        if not linea:
            break
        try:
            d = json.loads(linea)
            aviso(d["texto"], d.get("fraccion"))
        except (ValueError, KeyError, TypeError):
            continue


def lanzar(datos, aviso):
    """Pide autorización, sigue el progreso y devuelve el informe de ``proceso.crear``."""
    if sys.platform != "darwin":
        raise RuntimeError(idioma.t("am.solo_macos"))
    with tempfile.TemporaryDirectory(prefix="msxsdmaker_") as tmp:
        trabajo = os.path.join(tmp, "trabajo.json")
        progreso = os.path.join(tmp, "progreso.jsonl")
        resultado = os.path.join(tmp, "resultado.json")
        with open(trabajo, "w", encoding="utf-8") as f:
            json.dump(datos, f, ensure_ascii=False)
        # Los crea el usuario: el ayudante root sólo los abre y no deja ficheros con otro propietario.
        open(progreso, "w", encoding="utf-8").close()
        open(resultado, "w", encoding="utf-8").close()
        orden = shlex.join(_comando_ayudante(trabajo))
        guion = "do shell script %s with administrator privileges" % _cadena_applescript(orden)
        p = subprocess.Popen(["/usr/bin/osascript", "-e", guion], stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, text=True)
        with open(progreso, "r", encoding="utf-8") as f:
            while p.poll() is None:
                _leer_progreso(f, aviso)
                time.sleep(0.1)
            _leer_progreso(f, aviso)
        salida, error = p.communicate()
        if p.returncode:
            # El ayudante deja una explicación estructurada incluso cuando termina con error. Mostrarla antes
            # que el mensaje genérico de osascript hace útiles los fallos de desmontaje, identidad o escritura.
            try:
                with open(resultado, "r", encoding="utf-8") as f:
                    r_error = json.load(f)
                if isinstance(r_error, dict) and not r_error.get("ok") and r_error.get("error"):
                    raise RuntimeError(r_error["error"])
            except RuntimeError:
                raise
            except (OSError, ValueError, TypeError):
                pass
            detalle = (error or salida or "").strip()
            if "(-128)" in detalle or "cancel" in detalle.lower():
                raise PermissionError(idioma.t("am.cancelado"))
            raise PermissionError(detalle or idioma.t("am.sin_permisos"))
        try:
            with open(resultado, "r", encoding="utf-8") as f:
                r = json.load(f)
        except (OSError, ValueError) as e:
            raise RuntimeError(idioma.t("am.resultado_no_valido", e))
        if not r.get("ok"):
            raise RuntimeError(r.get("error") or idioma.t("am.no_ha_podido"))
        for texto in r.get("avisos", []):
            aviso(texto, None)
        return r["informe"]


def _plan(datos):
    out = []
    for p in datos:
        out.append(particiones.Particion(int(p["numero"]), int(p["lba"]), int(p["sectores"]), int(p["tipo"]),
                                         bool(p.get("activa")), p.get("lba_ebr")))
    if not out or [p.numero for p in out] != list(range(1, len(out) + 1)):
        raise ValueError(idioma.t("am.plan"))
    return out


def _datos_ocm(datos):
    if not datos:
        return None
    pack = ocm.abrir(datos["ruta"])
    problemas = pack.problemas()
    if problemas:
        raise ValueError(idioma.t("am.pack_no_vale", "; ".join(problemas[:3])))
    bios = [(str(nombre), ocm.receta(receta)) for nombre, receta in datos["bios"]]
    ocm.comprobar_lista(bios)
    return {"pack": pack, "bios": bios}


def _informe_json(informe):
    r = dict(informe)
    r["particiones"] = [dict(p, geometria=str(p["geometria"])) for p in informe["particiones"]]
    return r


def ejecutar(ruta_trabajo):
    """Entrada de la copia privilegiada. Devuelve un código de salida para ``MSXsdmaker.py``."""
    resultado = os.path.join(os.path.dirname(os.path.abspath(ruta_trabajo)), "resultado.json")
    progreso = os.path.join(os.path.dirname(os.path.abspath(ruta_trabajo)), "progreso.jsonl")

    def guardar(d):
        with open(resultado, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False)

    try:
        if sys.platform != "darwin" or os.geteuid() != 0:
            raise PermissionError(idioma.t("am.necesita_admin"))
        with open(ruta_trabajo, "r", encoding="utf-8") as f:
            d = json.load(f)
        if d.get("idioma") in idioma.TABLAS:       # el de la ventana, no el de esta copia (que corre como root)
            idioma.fijar(d["idioma"])
        if d.get("formato") != 1:
            raise ValueError(idioma.t("am.formato"))
        tarjeta = d["tarjeta"]
        plan = _plan(d["plan"])
        sistema = d["sistema"]
        if sistema not in contenido.SISTEMAS:
            raise ValueError(idioma.t("am.sistema"))
        datos_ocm = _datos_ocm(d.get("ocm"))
        maquina = "ocm" if datos_ocm else "fpga"
        validos = {g[0] for g in contenido.grupos_de(maquina)}
        grupos = set(d.get("grupos", []))
        if not grupos <= validos:
            raise ValueError(idioma.t("am.grupos"))
        opciones = contenido.opciones_n3(d.get("opciones"))

        with open(progreso, "a", encoding="utf-8", buffering=1) as log:
            def aviso(texto, fraccion=None):
                log.write(json.dumps({"texto": texto, "fraccion": fraccion}, ensure_ascii=False) + "\n")

            dev = dispositivos.DiscoMacOS(int(tarjeta["numero"]), esperada=tarjeta)
            try:
                informe = proceso.crear(dev, plan, sistema, grupos, str(d.get("etiqueta") or "MSX"), aviso,
                                         opciones=opciones, ocm=datos_ocm)
            finally:
                dev.cerrar()
            avisos = [dev.aviso_cierre] if dev.aviso_cierre else []
        guardar({"ok": True, "informe": _informe_json(informe), "avisos": avisos})
        return 0
    except Exception as e:
        try:
            guardar({"ok": False, "error": "%s: %s" % (type(e).__name__, e)})
        except Exception:
            pass
        return 1
