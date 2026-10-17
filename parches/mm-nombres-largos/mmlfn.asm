; MMLFN 2: nombres largos (VFAT) en Multi Mente 2.07_A
;
; - La lista de ficheros ensena en cada hueco los 12 primeros caracteres del nombre largo
;   (con ">" en la posicion de la "\" de las carpetas si el nombre sigue).
; - En File info, el campo "Name:" ensena el nombre largo entero (o 20 + "..." + 8).
;
; Ensamblar con pasmo (--hex) y aplicar con parchear.py. Va en estos sitios de MM.COM:
;   3D07h-3D2Ah  codigo muerto de MM: lo que quedaba de su lector de directorios por
;   3D60h-3DDDh  sectores (solo FAT12), que un JP incondicional en 3D5Dh salta. 3DDEh
;   3DDFh-3E02h  no se toca (MM y MM.EXE lo escriben); 3E03h+ lo usan overlays de MM.EXE.
;   5CF4h-5FBEh  detras del final de MM.COM: File info (la version 1). MM no usa esa zona.
;   5FBFh-       el arranque. Al cargar cae donde MM pone luego las marcas (5FBFh), su
;                _DPARM (5FDFh) y los registros (5FFFh+): copia a CB92h el codigo de la
;                pagina 3 y salta a MM.
;   CB92h-       la pagina 3: la pasada por el directorio y lo que lee la tabla. MM usa
;                hasta CB91h (57DDh) y deja el resto para la pila.
;   Segmento     el ultimo de los que se queda MM para copiar: la tabla de nombres
;                (8000h-9FFFh: 256 x 32), el nombre que se junta (A000h), la tabla de
;                conversion de caracteres (A200h), los clusters de la carpeta (A300h) y 8
;                sectores del directorio (B000h-BFFFh). Va en la pagina 2 solo mientras se usa.
; Y se desvian estos sitios:
;   0100h  JP 5CC4h      -> JP start     (el arranque)
;   586Fh  LD (HL),FFh / LD A,(F24Fh) -> CALL takeseg (el segmento para la tabla)
;   3E4Ah  LD HL,5FFFh   -> CALL lstart  (empieza un listado: la tabla deja de valer)
;   3E88h  LD DE,C935h   -> JP hookfib   (cada registro: la marca y donde esta la entrada)
;   3E82h  LD HL,(3E8Ch) -> JP pass      (fin del listado: pasada por el directorio)
;   33BFh  CALL 1376h    -> CALL lstname (la lista: el nombre de cada elemento)
;   34C3h  CALL 36C4h    -> CALL prep    (File info: borra la marca de "nombre ancho")
;   34D5h  CALL 13BAh    -> CALL tname   (File info: el nombre)
;   3547h  CALL 35C3h    -> CALL mydate  (la fecha; no se pinta si el nombre largo la tapa)
; Si no cabe en la pagina 3, el arranque deja los sitios de la pagina 3 como en la version 1
; (nombre largo solo en File info, leyendo el disco).
;
; Solo lee. Los registros de MM son entradas de directorio de 32 bytes (5FFFh + 32*n, al
; listar en el orden del directorio) en los que MM no usa los bytes 12-21. Al listar, hookfib
; guarda ahi una marca y la posicion de la entrada. Al acabar el listado, la pasada lee el
; directorio con _RDDRV (8 sectores cada vez), junta las entradas LFN y casa cada 8.3 con el
; registro que toca por el nombre (los dos van en el mismo orden). Para cada registro la
; tabla guarda el checksum de su 8.3 y el nombre tal como se pinta (hasta 31 caracteres), y
; el registro guarda su entrada de la tabla (MM mueve los registros enteros al ordenar); la
; lista y File info lo copian de alli. Si la tabla no lo
; sabe (sin segmento, registro sin casar o cambiado), File info lo busca en el disco como en
; la version 1: lee ese sector y el anterior y junta las entradas LFN que preceden a la 8.3
; si su checksum cuadra, o recorre el directorio (_FFIRST de "." para el cluster y _GETCLUS;
; la raiz con el _DPARM de MM). Sin Nextor (sin _RDDRV) o si algo falla, se pinta el 8.3.

BDOS            equ     0005h
POS             equ     1371h           ; x (1371h), y (1372h) del texto
COLVAR          equ     15FAh           ; color actual (lo guarda 164Eh)
PRLST           equ     1376h           ; pinta el 8.3 de la lista (registro HL)
PR83            equ     13BAh           ; pinta el nombre 8.3 del registro HL
PRCHR           equ     15A8h           ; pinta A (>= 20h) en POS y avanza x en 3
SETCOL          equ     164Eh
LSTMARK         equ     33D0h           ; 3395h despues de pintar la marca de carpeta
ATTR            equ     56E2h           ; atributo del elemento que se pinta (33A1h)
GETREC          equ     36C4h
PRDATE          equ     35C3h
RECPTR          equ     3E8Ch           ; registro que esta rellenando 3E88h
FIB             equ     0C934h          ; el FIB de MM al listar
PATH            equ     5780h           ; ruta de MM: "X:\..." (PATH+3 = 0 en la raiz)
DPB             equ     5FDFh           ; el _DPARM que hace MM al leer el directorio
REC0            equ     5FFFh           ; el primer registro
MMSTART         equ     5CC4h           ; el arranque de MM (lo que habia en 0100h)
MMDEFER         equ     0651h           ; la rutina de errores de disco de MM (588Bh)
MMABORT         equ     056Ah           ; la de abort que pone MM para listar (0786h)
MAINLST         equ     07AEh           ; la vuelta del listado de siempre (07ABh)
PUT_P2          equ     0C824h          ; las rutinas del mapper que copia MM (5844h)
GET_P2          equ     0C827h
EXTBIO          equ     0FFCAh

_SETDTA         equ     1Ah
_CURDRV         equ     19h
_FFIRST         equ     40h
_DEFAB          equ     63h
_DEFER          equ     64h
_RDDRV          equ     73h
_GETCLUS        equ     7Eh

MARCA           equ     0A5h            ; registro+12 = MARCA: +13..17 = FIB+45..49
RSLOT           equ     18              ; registro+18: su entrada en la tabla, si
RMARK           equ     19              ; registro+19 = MARCA (lo pone la pasada)
NAMEW           equ     12              ; ancho normal del campo Name (8.3)
WIDEW           equ     31              ; ancho con la fecha tapada (hasta el borde)
HEADW           equ     20              ; recortado: 20 + "..." + 8
TAILW           equ     8
LSTW            equ     12              ; caracteres de cada hueco de la lista
LFNSEQ          equ     20              ; 20 partes x 13 = 260 caracteres
LFNSZ           equ     LFNSEQ*13+1
FRAMESZ         equ     512+LFNSZ       ; sector + nombre, en la pila (File info sin tabla)
STKMIN          equ     (p3fin+16Eh+0FFh)/256
                                        ; el marco no baja de ahi: deja sitio para el
                                        ; codigo de la pagina 3 y, debajo del marco, para
                                        ; la pila de lo que se llama e interrupciones
STKMIN1         equ     0CDh            ; lo mismo sin la pagina 3 (MM usa hasta CB91h)
P3ORG           equ     0CB92h          ; donde se copia el codigo de la pagina 3
STKNEED         equ     300h            ; pila de MM que tiene que caber encima
TABLA           equ     8000h           ; en el segmento: 256 entradas de 32 bytes, una
                                        ; por registro (la n del registro 5FFFh+32*n al
                                        ; listar): +0 checksum del 8.3, +1 el nombre (0 =
                                        ; sin nombre largo), hasta 31 + 0
NOMBRE          equ     0A000h          ; el nombre que se junta (261)
CONVT           equ     0A200h          ; UTF-16 con el byte alto a 0 -> lo que se pinta
CLIST           equ     0A300h          ; el primer sector de cada cluster de la carpeta
CLEND           equ     SECBUF          ; (832 clusters como mucho)
SECBUF          equ     0B000h          ; 8 sectores del directorio
LOOKAH          equ     4               ; registros que se miran por delante al casar

; un caracter UTF-16 de HL a DE (HL += 2), con la tabla de conversion (B = su pagina)
PCHR            macro
                ld      c,(hl)
                inc     l
                ld      a,(hl)
                inc     l
                or      a
                call    nz,pc_hi
                ld      a,(bc)
                ld      (de),a
                inc     de
                endm

; ================================================================ 3D07h
                org     3D07h

; 3E88h: MM va a copiar al registro el FIB que acaba de encontrar
hookfib:        ld      hl,(RECPTR)
                ld      de,12
                add     hl,de
                ld      (hl),MARCA
                inc     hl
                ex      de,hl
                ld      hl,FIB+45       ; E_LEFT, S_LEFT, sector (bits 16-23, 0-15)
                ld      bc,5
                ldir
                ld      de,FIB+1        ; lo que habia en 3E88h
                jp      3E8Bh

; pinta A espacios
spaces:         or      a
                ret     z
                ld      b,a
spc1:           ld      a,' '
                call    PRCHR
                djnz    spc1
                ret
fin3d07:

; ================================================================ 3D60h
                org     3D60h

; UTF-16 (A = alto, C = bajo) -> caracter que se puede pintar (0 = fin)
conv:           or      a
                jr      nz,conv_hi
                ld      a,c
                or      a
                ret     z
                cp      20h
                jr      c,conv_q
                cp      7Fh
                ret     c
                sub     0C0h
                jr      c,conv_q
                ld      hl,latin1
                add     a,l
                ld      l,a
                jr      nc,conv1
                inc     h
conv1:          ld      a,(hl)
                ret
conv_hi:        inc     a               ; FFFFh = relleno
                jr      nz,conv_q
                ld      a,c
                inc     a
                ret     z
conv_q:         ld      a,'?'
                ret

offs:           db      1,3,5,7,9,14,16,18,20,22,24,28,30
latin1:         db      "AAAAAAACEEEEIIIIDNOOOOOxOUUUUYTs"      ; C0h-DFh
                db      "aaaaaaaceeeeiiiidnooooo/ouuuuyty"      ; E0h-FFh
datestr:        db      "Date: "
dotstr:         db      ".",0
; variables de un byte (aqui por falta de sitio en 5CF4h)
wide:           db      0               ; 1: el nombre largo tapa la fecha
expect:         db      0               ; parte LFN que toca; FFh = ninguna
chk:            db      0               ; checksum LFN del 8.3 buscado
drive:          db      0               ; unidad actual (0 = A:)
st:             db      0               ; bit 0: se llego a la entrada; bit 1: cadena cortada
fin3d60:

; ================================================================ 3DDFh
                org     3DDFh

; 34C3h
prep:           push    af
                xor     a
                ld      (wide),a
                pop     af
                jp      GETREC

; pinta B caracteres de HL (para en el 0); C = los pintados
prn:            ld      c,0
                ld      a,b
                or      a
                ret     z
prn1:           ld      a,(hl)
                or      a
                ret     z
                call    PRCHR
                inc     hl
                inc     c
                djnz    prn1
                ret

; el DTA de siempre (lo que heredan los programas que lanza MM)
dta80:          ld      de,80h
                ld      c,_SETDTA
                jp      BDOS
target:         dw      0               ; el registro que se pinta
fin3ddf:

; ================================================================ 5CF4h
                org     5CF4h

; ---------------------------------------------------------------- File info sin tabla
; HL = DE = registro (nombre 8.3 de 11 bytes); POS en el valor de "Name:".
; Al volver, B+C = espacios que pinta MM para acabar el campo (como 13BAh).
name:           push    ix
                push    hl
                push    de
                ld      (target),hl
                ld      a,(hl)
                cp      '.'
                jr      z,no
                ld      de,12           ; sin la marca de hookfib (el registro de
                add     hl,de           ; relleno que hace MM tras abortar un error
                ld      a,(hl)          ; de disco al listar) no se toca el disco
                cp      MARCA
                jr      nz,no
                ld      hl,-FRAMESZ
                add     hl,sp
                ld      a,h
stkcp:          cp      STKMIN          ; (STKMIN1 si no se ha copiado la pagina 3)
                jr      c,no
                ld      (frame),hl
                ld      de,512
                add     hl,de
                ld      (lfnp),hl
                ld      (savesp),sp
                ld      hl,(frame)
                ld      sp,hl
                call    find            ; NC: encontrado
                push    af
                call    dta80
                ld      hl,2059h        ; por si un error de disco movio el texto
                ld      (POS),hl
                pop     af
                call    nc,show         ; se pinta con el marco aun reservado
                ld      sp,(savesp)
                pop     de
                pop     hl
                pop     ix
                ret     nc
                jp      PR83
no:             pop     de
                pop     hl
                pop     ix
                jp      PR83

; pinta el nombre largo de (lfnp); vuelve NC y con BC como 13BAh
show:           ld      hl,(lfnp)
                ld      b,0
len:            ld      a,(hl)
                or      a
                jr      z,lenok
                inc     hl
                inc     b
                jr      nz,len
                dec     b               ; 255 como mucho
lenok:          ld      hl,(lfnp)
                ld      a,b
                cp      NAMEW+1
                jr      nc,ancho
                call    prn             ; cabe en el campo normal
                ld      a,NAMEW
                sub     c
                ld      b,a
                ld      c,0
                or      a
                ret
ancho:          ld      a,1
                ld      (wide),a
                ld      a,b
                cp      WIDEW+1
                jr      nc,recorta
                call    prn
                ld      a,WIDEW
                sub     c
                call    spaces
                jr      fin
recorta:        push    bc
                ld      b,HEADW
                call    prn
                ld      b,3
puntos:         ld      a,'.'
                call    PRCHR
                djnz    puntos
                pop     bc
                ld      a,b
                sub     TAILW
                ld      e,a
                ld      d,0
                ld      hl,(lfnp)
                add     hl,de
                ld      b,TAILW
                call    prn
fin:            ld      bc,0
                or      a
                ret

; ---------------------------------------------------------------- 3547h
; DE = registro+18h, POS = 2098h. Si el nombre largo tapa la fecha no se pinta;
; si no, se repone "   Date: " por si lo habia tapado el anterior (MM pinta 12
; posiciones de nombre y deja en blanco la 13.a, 207Dh).
mydate:         ld      a,(wide)
                or      a
                ret     nz
                push    de
                ld      hl,207Dh
                ld      (POS),hl
                ld      a,3
                call    spaces
                ld      a,(COLVAR)
                push    af
                ld      a,6             ; el color de las etiquetas
                call    SETCOL
                ld      hl,datestr
                ld      b,6
                call    prn
                pop     af
                call    SETCOL
                pop     de
                ld      hl,2098h
                ld      (POS),hl
                jp      PRDATE

; ---------------------------------------------------------------- busqueda
; Vuelve NC con el nombre largo en (lfnp), o C si no lo hay.
find:           ld      hl,(target)     ; checksum LFN del 8.3: las cadenas LFN
                ld      b,11            ; de otros ficheros se saltan sin copiarlas
                xor     a
f_sum:          rrca
                add     a,(hl)
                inc     hl
                djnz    f_sum
                ld      (chk),a
                ld      c,_CURDRV
                call    BDOS
                ld      (drive),a
                ld      de,(frame)
                ld      c,_SETDTA
                call    BDOS
                ld      hl,0
                ld      (clus),hl
                ld      (sect+2),hl
                ld      a,0FFh
                ld      (expect),a
                ld      hl,(target)     ; atajo: la posicion que guardo hookfib
                ld      de,13           ; (name ya ha visto la marca)
                add     hl,de
                ld      c,(hl)          ; entradas que quedan en el sector
                inc     hl
                ld      b,(hl)          ; sectores que quedan en el cluster
                inc     hl
                ld      a,(hl)
                ld      (sect+2),a
                inc     hl
                ld      e,(hl)
                inc     hl
                ld      d,(hl)          ; DE = sector (bits 0-15)
                ld      hl,(DPB+13)     ; primer sector de la raiz
                ld      a,(PATH+3)
                or      a
                jr      z,f_raiz
                ld      a,(DPB+3)       ; sectores por cluster: si quedan todos
                cp      b               ; es el primero del cluster
                jr      nz,f_ant
                ld      a,c             ; y si es su primera entrada, la cadena LFN
                sub     16              ; esta en el cluster anterior: a recorrer
                jr      z,full
                xor     a               ; Z: sin sector anterior
                jr      f_ant
f_raiz:         sbc     hl,de           ; o el primero de la raiz
f_ant:          ld      hl,1
                jr      z,f_uno         ; sin sector anterior a mano
                ld      a,d
                or      e
                jr      nz,f_dec
                ld      a,(sect+2)
                dec     a
                ld      (sect+2),a
f_dec:          dec     de              ; se empieza en el anterior
                inc     hl
f_uno:          ld      (left),hl
                ld      (sect),de
                xor     a
                ld      (st),a
                call    rdsec
                ret     nc              ; encontrado
                ld      a,(st)
                dec     a               ; se llego a la entrada y la cadena no
                scf                     ; empezaba antes: no tiene nombre largo
                ret     z

full:           ld      a,0FFh          ; recorrer el directorio desde el principio
                ld      (expect),a
                ld      hl,0
                ld      a,(PATH+3)      ; en la raiz no se busca "." (la recorreria)
                or      a
                jr      z,f_root
                ld      ix,(frame)      ; FIB en el marco
                ld      de,dotstr
                ld      b,10h
                ld      c,_FFIRST
                call    BDOS
                or      a
                jp      nz,nf           ; sin "." (disco cambiado...): el 8.3
                ld      l,(ix+19)
                ld      h,(ix+20)
f_root:         ld      a,h
                or      l
                jr      nz,nextclus
                ld      hl,(DPB+13)     ; raiz de FAT16: sectores fijos
                ld      (sect),hl
                ld      hl,0
                ld      (sect+2),hl
                ld      hl,(DPB+7)      ; entradas / 16
                ld      b,4
div16:          srl     h
                rr      l
                djnz    div16
                ld      (left),hl
                jr      rdsec

nextclus:       ex      de,hl           ; DE = cluster
                ld      hl,(frame)
                xor     a
                ld      c,_GETCLUS
                call    BDOS
                or      a
                jr      nz,nf
                ld      hl,(frame)
                ld      de,4
                add     hl,de
                ld      de,sect
                ld      bc,4
                ldir                    ; primer sector del cluster
                ld      e,(hl)
                inc     hl
                ld      d,(hl)          ; DE = siguiente cluster
                inc     hl
                ld      a,(hl)          ; sectores por cluster
                inc     hl
                bit     3,(hl)          ; ultimo cluster
                jr      z,nc1
                ld      de,0
nc1:            ld      (clus),de
                ld      l,a
                ld      h,0
                ld      (left),hl

; lee (left) sectores desde (sect) y luego los clusters que siga (clus)
rdsec:          ld      a,(drive)
                ld      b,1
                ld      de,(sect)
                ld      hl,(sect+2)
                ld      c,_RDDRV
                call    BDOS
                or      a
                jr      nz,nf
                ld      hl,sect
                ld      b,4
inc32:          inc     (hl)
                jr      nz,rd1
                inc     hl
                djnz    inc32
rd1:            ld      ix,(frame)
                ld      b,16
scan:           push    bc
                call    entry
                pop     bc
                ret     z               ; Z: fin (C = no esta, NC = encontrado)
                ld      de,32
                add     ix,de
                djnz    scan
                ld      hl,(left)
                dec     hl
                ld      (left),hl
                ld      a,h
                or      l
                jr      nz,rdsec
                ld      hl,(clus)
                ld      a,h
                or      l
                jr      nz,nextclus
nf:             scf
                ret

; IX = entrada. Vuelve NZ para seguir, o Z con C (no esta) / NC (encontrado).
entry:          ld      a,(ix+0)
                or      a
                jr      z,e_nf          ; fin del directorio
                cp      0E5h
                jr      z,e_reset       ; borrada
                ld      a,(ix+11)
                cp      0Fh
                jr      z,e_lfn
                push    ix
                pop     hl
                ld      de,(target)
                ld      b,11
e_cmp:          ld      a,(de)
                cp      (hl)
                jr      nz,e_reset      ; otra entrada
                inc     hl
                inc     de
                djnz    e_cmp
                ld      hl,st
                set     0,(hl)          ; se llego a la entrada
                ld      a,(expect)      ; LFN completo?
                or      a
                jr      nz,e_nf
                ret                     ; Z, NC
e_nf:           xor     a
                scf                     ; Z, C
                ret
e_cont:         ld      hl,st
                set     1,(hl)          ; una parte suelta de la cadena buscada
e_reset:        ld      a,0FFh
                ld      (expect),a
                or      a               ; NZ
                ret

e_lfn:          ld      a,(ix+13)
                ld      hl,chk
                cp      (hl)
                jr      nz,e_reset      ; de otro fichero
                ld      a,(ix+0)
                bit     6,a
                jr      z,e_lfn2
                and     1Fh             ; la ultima parte va la primera
                jr      z,e_reset
                cp      LFNSEQ+1
                jr      nc,e_reset
                ld      (expect),a
                call    mul13
                ld      (hl),0          ; fin de cadena tras la ultima parte
                ld      a,(ix+0)
e_lfn2:         and     1Fh
                jr      z,e_reset       ; parte 0: no existe (directorio estropeado)
                ld      hl,expect
                cp      (hl)
                jr      nz,e_cont
                dec     (hl)            ; la siguiente sera la anterior
                ld      a,(hl)          ; = numero de parte - 1
                call    mul13
                ex      de,hl
                ld      hl,offs
                ld      b,13
e_chr:          push    bc
                push    hl
                ld      c,(hl)
                ld      b,0
                push    ix
                pop     hl
                add     hl,bc
                ld      c,(hl)
                inc     hl
                ld      a,(hl)
                call    conv
                ld      (de),a
                inc     de
                pop     hl
                inc     hl
                pop     bc
                djnz    e_chr
                or      1               ; NZ
                ret

; HL = lfnp + A*13
mul13:          ld      l,a
                ld      h,0
                ld      c,l
                ld      b,h
                add     hl,hl
                add     hl,bc           ; 3
                add     hl,hl
                add     hl,hl           ; 12
                add     hl,bc           ; 13
                ld      bc,(lfnp)
                add     hl,bc
                ret

fincod:
; variables (no van en el fichero)
frame           equ     fincod
lfnp            equ     frame+2
savesp          equ     lfnp+2
clus            equ     savesp+2
left            equ     clus+2
sect            equ     left+2
finvar          equ     sect+4

; ================================================================ 5FBFh: arranque
; Corre una vez, donde lo deja la carga: luego MM escribe aqui sus marcas y registros.
                org     5FBFh

start:          ld      hl,(6)          ; cima del TPA: tiene que caber el codigo
                ld      de,p3fin+STKNEED ; de la pagina 3 y la pila de MM encima
                or      a
                sbc     hl,de
                jr      c,st_no
                ld      hl,img
                ld      de,P3ORG
                ld      bc,p3end-P3ORG
                ldir
                jp      MMSTART

; no cabe: los sitios de la pagina 3 vuelven a lo de la version 1
st_no:          ld      a,STKMIN1
                ld      (stkcp+1),a
                ld      hl,orig
                ld      b,6
st1:            ld      e,(hl)
                inc     hl
                ld      d,(hl)
                inc     hl
                push    bc
                ld      bc,3
                ldir
                pop     bc
                djnz    st1
                jp      MMSTART

orig:           dw      3E4Ah
                db      21h,0FFh,5Fh    ; LD HL,5FFFh
                dw      3E82h
                db      2Ah,8Ch,3Eh     ; LD HL,(3E8Ch)
                dw      33BFh
                db      0CDh,76h,13h    ; CALL 1376h
                dw      34D5h
                db      0CDh            ; CALL name
                dw      name
                dw      586Fh
                db      36h,0FFh,3Ah    ; LD (HL),FFh / LD A,(F24Fh)
                dw      5872h
                db      4Fh,0F2h,32h
img:                                    ; aqui sigue en el fichero la pagina 3

; ================================================================ CB92h: pagina 3
                org     P3ORG

; ---------------------------------------------------------------- 586Fh
; MM acaba la lista de los segmentos que se ha quedado (C831h, hasta 64, para copiar):
; el ultimo es para la tabla. Pedirlo en el arranque no vale: MM hace _FORK al empezar
; (5783h) y lo que se pide antes no se libera con el _JOIN de la vuelta de un programa.
takeseg:        ld      (hl),0FFh       ; lo que habia en 586Fh
                ld      a,l
                cp      33h             ; si tiene menos de 2 (128 KB) se le deja el
                jr      c,tk1           ; suyo y la lista sigue con el 8.3
                dec     hl
                ld      a,(hl)
                ld      (hl),0FFh
                ld      (segm),a
                call    GET_P2          ; en el segmento, la tabla de conversion de
                push    af              ; los caracteres: ASCII, las latinas sin
                ld      a,(segm)        ; acento (de latin1) y lo demas "?"
                call    PUT_P2
                ld      hl,CONVT
                xor     a
tk_cv:          ld      (hl),'?'
                cp      20h
                jr      c,tk_cv1
                cp      7Fh
                jr      nc,tk_cv1
                ld      (hl),a
tk_cv1:         inc     l
                inc     a
                jr      nz,tk_cv
                ld      (hl),a          ; 0: fin del nombre
                ld      hl,latin1
                ld      de,CONVT+0C0h
                ld      bc,64
                ldir
                pop     af
                call    PUT_P2          ; la de antes
tk1:            ld      a,(0F24Fh)      ; lo que habia en 5871h
                ret

; ---------------------------------------------------------------- 3E4Ah
; empieza un listado: la tabla ya no vale
lstart:         xor     a
                ld      (tblok),a
                ld      hl,REC0         ; lo que habia en 3E4Ah
                ret

; ---------------------------------------------------------------- 3E82h
; fin del listado: pasada por el directorio para llenar la tabla
pass:           ld      hl,(RECPTR)     ; lo que habia en 3E82h: el fin de la lista
                ld      (hl),0
                ld      de,REC0+256*32  ; la tabla tiene sitio para 256 registros
                call    cphlde
                jr      c,ps0
                ex      de,hl
ps0:            ld      (recend),hl
                ld      a,(segm)
                or      a
                ret     z               ; sin segmento: la lista sigue con el 8.3
                ld      hl,0
                add     hl,sp
                ld      a,h
                cp      0C0h            ; con la pila en la pagina 2 no se puede
                ret     c               ; cambiar el segmento
                ld      a,(hl)          ; solo en el listado de siempre (07ABh), con
                cp      MAINLST and 0FFh ; MMABORT de rutina de abort: la que hay que
                ret     nz              ; reponer si se aborta (los otros, como 1AFFh,
                inc     hl              ; vuelven a listar por ahi)
                ld      a,(hl)
                cp      MAINLST/256
                ret     nz
                ld      hl,REC0
                call    firstok
                ret     z               ; ningun registro con nombre que buscar
                ld      (krec),hl
                ld      c,_CURDRV
                call    BDOS
                ld      (drive),a
                ld      hl,0
                ld      (left),hl
                ld      (sect+2),hl
                ld      a,(PATH+3)
                or      a
                jr      z,ps_root
                ld      hl,REC0         ; el primer cluster de la carpeta: el del
                ld      a,(hl)          ; registro de "." (el primero, si el filtro
                cp      '.'             ; de Wild no lo quita)
                jr      nz,ps_ff
                inc     hl
                ld      a,(hl)
                cp      ' '
                jr      nz,ps_ff
                ld      de,(REC0+26)
                jr      ps_cl
ps_ff:          ld      hl,-64          ; o el de "." con _FFIRST (FIB en la pila)
                add     hl,sp
                ld      sp,hl
                push    hl
                pop     ix
                ld      de,dotstr
                ld      bc,10h*256+_FFIRST
                call    BDOS
                ld      e,(ix+19)
                ld      d,(ix+20)
                ld      hl,64
                add     hl,sp
                ld      sp,hl
                or      a
                ret     nz              ; sin "." (disco cambiado...): el 8.3
ps_cl:          ld      a,d
                or      e
                jr      nz,ps_dta
ps_root:        ld      hl,(DPB+13)     ; raiz de FAT12/16: sectores seguidos
                ld      (sect),hl
                ld      hl,(DPB+7)      ; entradas / 16
                ld      b,4
ps_div:         srl     h
                rr      l
                djnz    ps_div
                ld      (left),hl
                ld      de,0
ps_dta:         ld      (clus),de
                ld      de,SECBUF
                ld      c,_SETDTA
                call    BDOS
                ld      hl,REC0         ; todos los registros: sin casar (hasta el
ps_ini:         ld      de,(RECPTR)     ; fin de la lista: el 257.o llega a la
                call    cphlde          ; pagina 2, que aun es la del TPA)
                jr      nc,ps_ini2
                ld      de,RMARK
                add     hl,de
                ld      (hl),0
                ld      de,32-RMARK
                add     hl,de
                jr      ps_ini
ps_ini2:        xor     a
                ld      (errf),a
                ld      de,deferh       ; un error de disco lo ve la pasada
                ld      c,_DEFER
                call    BDOS
                ld      de,abh          ; y si se aborta (STOP, Abort en el dialogo
                ld      c,_DEFAB        ; de MM), se deja todo como estaba
                call    BDOS
                call    GET_P2
                ld      (tpa2),a
                ld      a,(segm)
                call    PUT_P2
                ld      hl,NOMBRE
                ld      (lfnp),hl
                ld      a,0FFh
                ld      (expect),a
; la cadena de clusters de la carpeta (el primer sector de cada uno en CLIST),
; antes de leer: tras cada _RDDRV, Nextor vuelve a leer la FAT
                ld      hl,CLIST
                ld      (cend),hl
                ld      (cptr),hl
ps_gc:          ld      de,(clus)
                ld      a,d
                or      e
                jr      z,ps_rd
                ld      hl,gcbuf
                xor     a               ; la unidad actual
                ld      c,_GETCLUS
                call    BDOS
                or      a
                jp      nz,ps_err
                ld      a,(errf)
                or      a
                jp      nz,ps_err
                ld      hl,gcbuf+4
                ld      de,(cend)
                ld      bc,4
                ldir
                ld      (cend),de
                ld      e,(hl)
                inc     hl
                ld      d,(hl)          ; el siguiente
                inc     hl
                ld      a,(hl)
                ld      (spc),a         ; sectores por cluster
                inc     hl
                bit     3,(hl)          ; el ultimo de la cadena
                jr      z,ps_gc1
                ld      de,0
ps_gc1:         ld      (clus),de
                ld      hl,(cend)
                ld      de,CLEND
                call    cphlde
                jr      c,ps_gc         ; (y no mas de los que caben)
; de 8 en 8 sectores, sin pasar del cluster
ps_rd:          ld      hl,(left)
                ld      a,h
                or      l
                jr      nz,ps_rd1
                ld      hl,(cptr)       ; el siguiente cluster
                ld      de,(cend)
                call    cphlde
                jr      nc,ps_ok        ; no quedan
                ld      de,sect
                ld      bc,4
                ldir
                ld      (cptr),hl
                ld      a,(spc)
                ld      l,a
                ld      h,0
                ld      (left),hl
ps_rd1:         ld      a,h
                or      a
                ld      a,8
                jr      nz,ps_rd2
                cp      l
                jr      c,ps_rd2
                ld      a,l
ps_rd2:         ld      b,a             ; B = sectores (1-8)
                ld      e,a
                ld      d,0
                or      a
                sbc     hl,de
                ld      (left),hl
                push    bc
                ld      a,(drive)
                ld      de,(sect)
                ld      hl,(sect+2)
                ld      c,_RDDRV
                call    BDOS
                pop     bc
                or      a
                jr      nz,ps_err
                ld      a,(errf)
                or      a
                jr      nz,ps_err
                ld      hl,(sect)
                ld      e,b
                ld      d,0
                add     hl,de
                ld      (sect),hl
                jr      nc,ps_rd3
                ld      hl,(sect+2)
                inc     hl
                ld      (sect+2),hl
ps_rd3:         ld      a,b
                add     a,a
                add     a,a
                add     a,a
                add     a,a
                ld      b,a             ; B = entradas (16-128)
                ld      ix,SECBUF
ps_ent:         push    bc
                call    pentry
                pop     bc
                jr      z,ps_ok         ; fin del directorio o no quedan registros
                ld      de,32
                add     ix,de
                djnz    ps_ent
                jp      ps_rd
ps_ok:          ld      a,1
                jr      ps_out
ps_err:         xor     a
ps_out:         ld      (tblok),a
restore:        ld      a,(tpa2)        ; lo de MM: pagina 2, rutinas de error y de
                call    PUT_P2          ; abort y DTA
                ld      de,MMDEFER
                ld      c,_DEFER
                call    BDOS
                ld      de,MMABORT
                ld      c,_DEFAB
                call    BDOS
                jp      dta80

; abort durante la pasada (A y B: los errores): se repone lo de MM y se sigue con su
; rutina de abort
abh:            push    af
                push    bc
                call    restore
                pop     bc
                pop     af
                jp      MMABORT

; IX = entrada del directorio. Vuelve Z para acabar (fin del directorio o ya no
; quedan registros que casar) o NZ para seguir.
pentry:         ld      a,(ix+0)
                or      a
                ret     z               ; fin del directorio
                cp      0E5h
                jr      z,pe_rst        ; borrada
                cp      '.'
                jr      z,pe_rst        ; "." y ".."
                ld      a,(ix+11)
                cp      0Fh
                jr      z,pe_lfn
                bit     3,a
                jr      nz,pe_rst       ; etiqueta de volumen
                push    ix              ; una 8.3: tiene nombre largo si acaba de
                pop     hl              ; completarse una cadena con su checksum
                call    cksum
                ld      (ck83),a
                ld      hl,expect
                ld      b,(hl)
                ld      (hl),0FFh
                ld      hl,chk
                sub     (hl)
                or      b
                ld      (lfnok),a       ; 0: con nombre largo
                ld      hl,(krec)       ; se casa con el registro que toca
                call    cmp11
                jr      z,pe_hit
                ld      b,LOOKAH        ; o con uno de los siguientes (los que se
pe_la:          push    bc              ; saltan no estan en lo leido: se quedan
                call    nextrec         ; sin casar)
                pop     bc
                jr      z,pe_nz
                call    cmp11
                jr      z,pe_hit
                djnz    pe_la
pe_nz:          or      1               ; no es de la lista: se sigue
                ret
pe_hit:         ld      a,(ix+0)        ; HL = el registro: su checksum es el de la
                cp      5               ; entrada salvo si esta empieza por 05h (E5h)
                ld      a,(ck83)
                jr      nz,pe_h1
                push    hl
                call    cksum
                pop     hl
pe_h1:          push    hl
                ld      c,a
                ld      de,-REC0        ; su sitio en la tabla: el que tiene ahora
                add     hl,de           ; (32*n); va en el registro, que MM mueve
                add     hl,hl           ; entero al ordenar
                add     hl,hl
                add     hl,hl
                ld      a,h
                pop     hl
                push    hl
                ld      de,RSLOT
                add     hl,de
                ld      (hl),a
                inc     hl
                ld      (hl),MARCA
                pop     hl
                push    hl
                ld      de,TABLA-REC0
                add     hl,de
                ld      (hl),c          ; checksum del 8.3 del registro
                inc     hl
                ld      (hl),0          ; sin nombre largo
                ld      a,(lfnok)
                or      a
                call    z,fmt
                pop     hl
                call    nextrec         ; el siguiente que hay que casar
                ld      (krec),hl
                ret                     ; Z: ya no quedan, se acaba
pe_rst:         ld      a,0FFh
                ld      (expect),a
                or      a               ; NZ
                ret

pe_lfn:         ld      a,(ix+0)
                bit     6,a
                jr      z,pl_2
                and     1Fh             ; la ultima parte va la primera
                jr      z,pe_rst
                cp      LFNSEQ+1
                jr      nc,pe_rst
                ld      (expect),a
                ld      (nparts),a
                ld      c,(ix+13)
                ld      hl,chk
                ld      (hl),c
                call    mul13
                ld      (hl),0          ; fin de cadena tras la ultima parte
                ld      (dptr),hl
                ld      a,(ix+0)
pl_2:           and     1Fh
                jr      z,pe_rst        ; parte 0: no existe (directorio estropeado)
                ld      hl,expect
                cp      (hl)
                jr      nz,pe_rst       ; suelta o fuera de orden
                ld      a,(ix+13)
                ld      hl,chk
                cp      (hl)
                jr      nz,pe_rst       ; de otro fichero
                ld      hl,expect
                dec     (hl)
                ld      hl,(dptr)       ; cada parte va 13 caracteres antes
                ld      de,-13
                add     hl,de
                ld      (dptr),hl
                ex      de,hl
                push    ix
                pop     hl              ; las entradas van alineadas a 32 bytes:
                inc     l               ; dentro de una basta con INC L
                ld      b,CONVT/256     ; cada caracter UTF-16, con la tabla del
                rept    5               ; segmento; los caracteres 1-5 (+1..+10)
                PCHR
                endm
                inc     l
                inc     l
                inc     l
                rept    6               ; 6-11 (+14..+25)
                PCHR
                endm
                inc     l
                inc     l
                rept    2               ; 12 y 13 (+28..+31)
                PCHR
                endm
                or      1               ; NZ
                ret

; byte alto distinto de 0: C = 0 (fin) si es FFFFh, el relleno tras el fin, y si no
; C = 1 ("?" en la tabla)
pc_hi:          inc     a
                jr      nz,pc_q
                ld      a,c
                inc     a
                ld      c,a
                ret     z
pc_q:           ld      c,1
                ret

; HL = destino (entrada+1): el nombre de NOMBRE tal como se pinta, hasta 31
fmt:            push    hl
                ld      a,(nparts)      ; el fin esta en la ultima parte
                dec     a
                call    mul13
fm1:            ld      a,(hl)
                or      a
                jr      z,fm2
                inc     hl
                jr      fm1
fm2:            ld      de,-NOMBRE
                add     hl,de           ; HL = longitud
                ld      a,h
                or      a
                ld      a,l
                jr      z,fm3
                ld      a,255           ; 255 como mucho
fm3:            pop     de
                or      a
                ret     z               ; vacio: sin nombre largo
                ld      c,a
                ld      b,0
                ld      hl,NOMBRE
                cp      WIDEW+1
                jr      nc,fm_cut
                ldir                    ; cabe entero
                cp      WIDEW
                ret     z               ; 31: llena la entrada
                xor     a
                ld      (de),a
                ret
fm_cut:         ld      c,HEADW         ; los 20 primeros, "..." y los 8 ultimos
                ldir
                ex      de,hl
                ld      (hl),'.'
                inc     hl
                ld      (hl),'.'
                inc     hl
                ld      (hl),'.'
                inc     hl
                ex      de,hl
                sub     TAILW
                ld      c,a
                ld      hl,NOMBRE
                add     hl,bc
                ld      c,TAILW
                ldir
                ret

; HL = registro: el siguiente (nextrec) o este mismo (firstok) que se puede casar:
; con la marca de hookfib, sin la de etiqueta de volumen y que no sea "." ni "..".
; Z si no queda ninguno.
nextrec:        ld      de,32
                add     hl,de
firstok:        ld      de,(recend)
                call    cphlde
                jr      nc,fo_no
                push    hl
                ld      de,11
                add     hl,de
                bit     3,(hl)          ; etiqueta de volumen
                inc     hl
                ld      a,(hl)
                pop     hl
                jr      nz,nextrec
                cp      MARCA
                jr      nz,nextrec
                ld      a,(hl)
                cp      '.'
                jr      z,nextrec
                ret                     ; NZ
fo_no:          xor     a
                ret

; C si HL < DE
cphlde:         push    hl
                or      a
                sbc     hl,de
                pop     hl
                ret

; Z si el nombre de la entrada IX es el del registro HL (que se conserva)
cmp11:          push    hl
                push    bc
                push    ix
                pop     de
                ld      a,(de)
                cp      5               ; E5h se guarda como 05h
                jr      nz,c11a
                ld      a,0E5h
c11a:           ld      b,11
                jr      c11c
c11b:           inc     de
                inc     hl
                ld      a,(de)
c11c:           cp      (hl)
                jr      nz,c11x
                djnz    c11b
c11x:           pop     bc
                pop     hl
                ret

; A = checksum LFN de los 11 bytes de HL
cksum:          ld      b,11
                xor     a
ck1:            rrca
                add     a,(hl)
                inc     hl
                djnz    ck1
                ret

; errores de disco durante la pasada: el primero se ignora y la pasada lo ve en
; errf; si se repite (Nextor reintenta algunos), el dialogo de MM, con la pagina 2
; de siempre mientras dura: con Retry se vuelve a leer al segmento y con Abort se
; sale por abh
deferh:         push    af
                ld      a,(errf)
                inc     a
                ld      (errf),a
                cp      2
                jr      nc,df2
                pop     af
                ld      a,3             ; Ignore
                ret
df2:            ld      a,(tpa2)
                call    PUT_P2
                pop     af
                call    MMDEFER
                push    af
                ld      a,(segm)
                call    PUT_P2
                pop     af
                ret

; ---------------------------------------------------------------- tabla
; HL = registro. Vuelve C si la tabla no lo sabe (sin tabla, sin casar o el registro
; ha cambiado), Z si no tiene nombre largo y NZ con el nombre en ebuf+1.
getent:         ld      a,(tblok)
                sub     1
                ret     c               ; sin tabla
                ld      de,REC0+256*32
                call    cphlde
                ccf
                ret     c               ; fuera de la tabla
                push    hl
                ld      de,RMARK
                add     hl,de
                ld      a,(hl)
                cp      MARCA
                dec     hl
                ld      a,(hl)          ; su sitio en la tabla
                pop     hl
                scf
                ret     nz              ; sin casar
                push    af
                call    cksum
                ld      c,a
                pop     af
                ld      l,a
                ld      h,0
                add     hl,hl
                add     hl,hl
                add     hl,hl
                add     hl,hl
                add     hl,hl
                ld      de,TABLA
                add     hl,de
                ex      de,hl           ; DE = entrada
                ld      hl,0
                add     hl,sp
                ld      a,h
                cp      0C0h            ; con la pila en la pagina 2 no se puede
                ret     c               ; cambiar el segmento
                call    GET_P2
                ld      b,a
                ld      a,(segm)
                call    PUT_P2
                ex      de,hl
                ld      de,ebuf
                push    bc
                ld      bc,32
                ldir
                pop     bc
                ld      a,b
                call    PUT_P2
                ld      a,(ebuf)
                cp      c
                scf
                ret     nz              ; otro 8.3: el registro ha cambiado
                ld      a,(ebuf+1)
                or      a               ; NC; Z: sin nombre largo
                ret

; ---------------------------------------------------------------- 33BFh
; la lista: HL = DE = registro, POS al principio del hueco. Sin nombre largo, el 8.3
; de MM; con el, sus 12 primeros caracteres y en la 13.a la "\" de las carpetas o
; ">" si el nombre sigue; luego se vuelve a 3395h despues de la marca.
lstname:        push    hl
                push    de
                call    getent
                pop     de
                pop     hl
                jp      c,PRLST
                jp      z,PRLST
                ld      hl,ebuf+1
                ld      b,LSTW
                call    prn             ; C = los pintados
                ld      a,LSTW
                sub     c
                ld      b,' '
                jr      nz,ls0          ; acaba antes: espacios hasta la 12.a
                ld      a,(ebuf+1+LSTW)
                or      a
                jr      z,ls0           ; (A = 0: ningun espacio)
                ld      b,'>'           ; sigue
                xor     a
ls0:            push    bc
                call    spaces
                pop     bc
                ld      a,(ATTR)
                bit     4,a
                ld      a,5Ch
                jr      nz,ls1
                ld      a,b
ls1:            call    PRCHR
                pop     af              ; la vuelta a 33C2h
                jp      LSTMARK

; ---------------------------------------------------------------- 34D5h
; File info: HL = DE = registro. Lo de la tabla; si no lo sabe, lo de la version 1.
tname:          push    hl
                push    de
                call    getent
                pop     de
                pop     hl
                jp      c,name
                jp      z,PR83
                push    hl
                push    de
                ld      hl,ebuf+1
                ld      (lfnp),hl
                call    show
                pop     de
                pop     hl
                ret

tblok:          db      0               ; 1: la tabla es la del ultimo listado
segm:           db      0               ; segmento de la tabla (0 = ninguno)
ebuf:           ds      32,0            ; la entrada de la tabla que se pinta
                db      0               ; fin del nombre si tiene 31

p3end:
; variables (no van en el fichero)
tpa2            equ     p3end           ; el segmento de la pagina 2 durante la pasada
errf            equ     tpa2+1          ; errores de disco durante la pasada
lfnok           equ     errf+1
ck83            equ     lfnok+1         ; checksum de la entrada 8.3
spc             equ     ck83+1          ; sectores por cluster
cend            equ     spc+1           ; fin de CLIST
cptr            equ     cend+2          ; el siguiente cluster de CLIST
nparts          equ     cptr+2          ; partes de la cadena LFN
dptr            equ     nparts+1        ; donde va la parte LFN que toca
krec            equ     dptr+2         ; el siguiente registro que hay que casar
recend          equ     krec+2          ; el fin de los registros (o de la tabla)
gcbuf           equ     recend+2        ; lo que da _GETCLUS (16)
p3fin           equ     gcbuf+16
; parchear.py comprueba los limites de cada trozo
