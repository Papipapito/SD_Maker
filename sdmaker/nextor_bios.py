"""Creador de ROM Nextor 3, compatible con el formato de mknexrom 1.2 de Konamiman.

Combina el kernel base oficial con un driver Nextor 3 específico del hardware. También admite código de mapper,
un bloque extra de hasta 256 bytes, el parche para mappers de bancos de 8 KB y el inversor de teclas de arranque.
"""
from . import idioma

BANK_SIZE = 16 * 1024
MAPPER_SIZE = 48
EXTRA_SIZE = 256
EXTRA_OFFSET = 0x3ED0
BASE_BANK_COUNT_OFFSET = 0xFE
PAGE0_SIZE = 256
MAPPER_INIT_OFFSET = 0x07DC
MAPPER_8K_PATCH_OFFSET = 0x00F7
BOOT_KEYS_OFFSET = 0x0200
DRIVER_SIGNATURE = b"NEXTORv3_DRIVER"
DRIVER_MIN_SIZE = 256 + len(DRIVER_SIGNATURE) + 13 * 3
PACK_NEXTOR_OFFSET = 0x40000
PACK_NEXTOR_SIZE = 128 * 1024
PACK_SIZE = 512 * 1024

# Mapa fijo del pack MSXnano/MSXimus. Los bloques de menú se describen para poder
# inspeccionarlos, pero no se ofrecen como huecos libres: el core los necesita. El nombre de cada bloque es una clave de idioma.py (idioma.t(nombre)).
PACK_BLOCKS = [
    ("jis1", "nb.bloque.jis1", 0x00000, 128 * 1024, True),
    ("jis2", "nb.bloque.jis2", 0x20000, 128 * 1024, True),
    ("nextor", "nb.bloque.nextor", 0x40000, 128 * 1024, False),
    ("main", "nb.bloque.main", 0x60000, 32 * 1024, True),
    ("sub", "nb.bloque.sub", 0x68000, 16 * 1024, True),
    ("music_menu", "nb.bloque.music_menu", 0x6C000, 16 * 1024, True),
    ("menu2", "nb.bloque.menu2", 0x70000, 16 * 1024, False),
    ("free", "nb.bloque.free", 0x74000, 16 * 1024, False),
    ("network", "nb.bloque.network", 0x78000, 16 * 1024, True),
    ("logo", "nb.bloque.logo", 0x7C000, 16 * 1024, True),
]


def _bancos(datos):
    return (len(datos) + BANK_SIZE - 1) // BANK_SIZE


def crear_rom(base, driver, mapper=None, extra=None, direccion_8k=None, teclas=None):
    """Devuelve una ROM completa a partir de bytes. Lanza ValueError si una entrada no es compatible."""
    if len(base) <= BASE_BANK_COUNT_OFFSET:
        raise ValueError(idioma.t("nb.kernel_pequeno"))
    bancos_base = base[BASE_BANK_COUNT_OFFSET]
    if bancos_base == 0 or len(base) != bancos_base * BANK_SIZE:
        raise ValueError(idioma.t("nb.kernel_tam"))
    if len(driver) < DRIVER_MIN_SIZE or driver[PAGE0_SIZE:PAGE0_SIZE + len(DRIVER_SIGNATURE)] != DRIVER_SIGNATURE:
        raise ValueError(idioma.t("nb.driver_no_n3"))

    mapper_explicito = mapper is not None
    if mapper is None:
        codigo_mapper = base[BANK_SIZE - MAPPER_SIZE:BANK_SIZE]
    else:
        if not mapper:
            raise ValueError(idioma.t("nb.mapper_vacio"))
        if mapper[0] == 0xFF:
            if len(mapper) < 4:
                raise ValueError(idioma.t("nb.mapper8_incompleto"))
            if direccion_8k is None:
                direccion_8k = mapper[1] | mapper[2] << 8
            mapper = mapper[3:]
        if len(mapper) > MAPPER_SIZE:
            raise ValueError(idioma.t("nb.mapper_48"))
        codigo_mapper = mapper.ljust(MAPPER_SIZE, b"\0")

    if direccion_8k is not None and not 0x4000 <= direccion_8k < 0x8000:
        raise ValueError(idioma.t("nb.dir8k"))
    if teclas is not None and not 0 <= teclas <= 0xFFFF:
        raise ValueError(idioma.t("nb.teclas"))

    if extra is not None:
        if len(extra) > EXTRA_SIZE:
            raise ValueError(idioma.t("nb.extra_256"))
        for banco in (0, 3):
            zona = base[banco * BANK_SIZE + EXTRA_OFFSET:banco * BANK_SIZE + EXTRA_OFFSET + EXTRA_SIZE]
            if zona != bytes(EXTRA_SIZE):
                raise ValueError(idioma.t("nb.extra_usado", banco))

    total_bancos = bancos_base + _bancos(driver)
    if total_bancos > 256:
        raise ValueError(idioma.t("nb.bancos_256"))
    rom = bytearray(total_bancos * BANK_SIZE)
    rom[:len(base)] = base
    rom[len(base):len(base) + len(driver)] = driver

    pagina_0 = base[:PAGE0_SIZE - 1]
    for banco in range(bancos_base, total_bancos):
        inicio = banco * BANK_SIZE
        rom[inicio:inicio + PAGE0_SIZE - 1] = pagina_0
        rom[inicio + PAGE0_SIZE - 1] = banco

    inicio_mapper = 0 if mapper_explicito else bancos_base
    for banco in range(inicio_mapper, total_bancos):
        fin = (banco + 1) * BANK_SIZE
        rom[fin - MAPPER_SIZE:fin] = codigo_mapper
    if mapper_explicito:
        rom[MAPPER_INIT_OFFSET:MAPPER_INIT_OFFSET + MAPPER_SIZE] = codigo_mapper

    if direccion_8k is not None:
        parche = bytes((0x32, direccion_8k & 0xFF, direccion_8k >> 8))
        for banco in range(total_bancos):
            inicio = banco * BANK_SIZE + MAPPER_8K_PATCH_OFFSET
            rom[inicio:inicio + len(parche)] = parche

    if extra is not None:
        bloque = extra.ljust(EXTRA_SIZE, b"\0")
        for banco in (0, 3):
            inicio = banco * BANK_SIZE + EXTRA_OFFSET
            rom[inicio:inicio + EXTRA_SIZE] = bloque

    if teclas is not None:
        rom[BOOT_KEYS_OFFSET:BOOT_KEYS_OFFSET + 2] = teclas.to_bytes(2, "little")
    return bytes(rom)


def actualizar_pack_bios(pack, base):
    """Actualiza a 3.0 final el bloque Nextor de un pack MSXnano/MSXimus, conservando su driver y configuración."""
    if len(pack) not in (512 * 1024, 512 * 1024 + 6):
        raise ValueError(idioma.t("nb.pack_512"))
    viejo = pack[PACK_NEXTOR_OFFSET:PACK_NEXTOR_OFFSET + PACK_NEXTOR_SIZE]
    if len(viejo) != PACK_NEXTOR_SIZE:
        raise ValueError(idioma.t("nb.pack_sin_nextor"))
    bancos_base = viejo[BASE_BANK_COUNT_OFFSET]
    inicio_driver = bancos_base * BANK_SIZE
    if bancos_base == 0 or inicio_driver >= len(viejo):
        raise ValueError(idioma.t("nb.sin_kernel"))
    driver = viejo[inicio_driver:]
    if driver[PAGE0_SIZE:PAGE0_SIZE + len(DRIVER_SIGNATURE)] != DRIVER_SIGNATURE:
        raise ValueError(idioma.t("nb.pack_sin_driver"))

    mapper = viejo[BANK_SIZE - MAPPER_SIZE:BANK_SIZE]
    extra = viejo[EXTRA_OFFSET:EXTRA_OFFSET + EXTRA_SIZE]
    extra = extra if any(extra) else None
    teclas = int.from_bytes(viejo[BOOT_KEYS_OFFSET:BOOT_KEYS_OFFSET + 2], "little")
    parche = viejo[MAPPER_8K_PATCH_OFFSET:MAPPER_8K_PATCH_OFFSET + 3]
    valor_8k = parche[1] | parche[2] << 8
    direccion_8k = valor_8k if parche[0] == 0x32 and 0x4000 <= valor_8k < 0x8000 else None
    nuevo = crear_rom(base, driver, mapper=mapper, extra=extra, direccion_8k=direccion_8k, teclas=teclas)
    if len(nuevo) != PACK_NEXTOR_SIZE:
        raise ValueError(idioma.t("nb.kernel_128", len(nuevo) // 1024))
    salida = bytearray(pack)
    salida[PACK_NEXTOR_OFFSET:PACK_NEXTOR_OFFSET + PACK_NEXTOR_SIZE] = nuevo
    return bytes(salida)


def personalizar_pack(pack, reemplazos):
    """Sustituye bloques completos del pack, conservando su posible cola de configuración."""
    if len(pack) not in (PACK_SIZE, PACK_SIZE + 6):
        raise ValueError(idioma.t("nb.pack_512"))
    mapa = {clave: (nombre, offset, tamano, editable)
            for clave, nombre, offset, tamano, editable in PACK_BLOCKS}
    salida = bytearray(pack)
    for clave, datos in reemplazos.items():
        if clave not in mapa:
            raise ValueError(idioma.t("nb.bloque_desconocido", clave))
        nombre, offset, tamano, editable = mapa[clave]
        if not editable:
            raise ValueError(idioma.t("nb.protegido", idioma.t(nombre)))
        if len(datos) != tamano:
            raise ValueError(idioma.t("nb.tam_bloque", clave, len(datos), idioma.t(nombre), tamano))
        salida[offset:offset + tamano] = datos
    return bytes(salida)


def bloques_pack(pack):
    """Información y bytes de cada bloque de un pack válido."""
    if len(pack) not in (PACK_SIZE, PACK_SIZE + 6):
        raise ValueError(idioma.t("nb.pack_512"))
    return [(clave, nombre, offset, tamano, editable, pack[offset:offset + tamano])
            for clave, nombre, offset, tamano, editable in PACK_BLOCKS]
