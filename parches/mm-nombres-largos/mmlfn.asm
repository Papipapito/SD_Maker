; MMLFN: nombre largo (VFAT) en el campo "Name:" de File info de Multi Mente 2.07_A
;
; Ensamblar con pasmo (--hex) y aplicar con parchear.py. Va en estos sitios de MM.COM:
;   5CF4h-5FBEh  detras del final de MM.COM (se anade al fichero). MM no usa esa zona
;                (5FBFh son las marcas, 5FDFh su _DPARM y 5FFFh+ los registros).
;   3D07h-3D2Ah  codigo muerto de MM: lo que quedaba de su lector de directorios por
;   3D60h-3DDDh  sectores (solo FAT12), que un JP incondicional en 3D5Dh salta. 3DDEh
;   3DDFh-3E02h  no se toca (MM y MM.EXE lo escriben); 3E03h+ lo usan overlays de MM.EXE.
; Y se desvian cuatro sitios:
;   3E88h  LD DE,C935h -> JP hookfib  (al listar: guarda en el registro donde esta la entrada)
;   34C3h  CALL 36C4h  -> CALL prep   (File info: borra la marca de "nombre ancho")
;   34D5h  CALL 13BAh  -> CALL name   (pinta el nombre: el largo si lo hay, si no el 8.3)
;   3547h  CALL 35C3h  -> CALL mydate (la fecha; no se pinta si el nombre largo la tapa)
;
; Solo lee. Los registros de MM son entradas de directorio de 32 bytes en los que MM no
; usa los bytes 12-21: al listar se guarda ahi la posicion de la entrada (sector y
; sectores que quedan en el cluster, del FIB de Nextor 2.1). File info lee con _RDDRV
; ese sector y el anterior y junta las entradas LFN que preceden a la 8.3 si su checksum
; cuadra. Si no la encuentra ahi (o la cadena LFN empieza antes), recorre el directorio
; (_FFIRST de "." para el cluster y _GETCLUS; la raiz con el _DPARM de MM). Sin Nextor
; (sin _RDDRV) o si algo falla, se pinta el 8.3 como siempre. El sector y el nombre van
; en la pila (MM usa hasta CB92h y deja el resto para la pila).

BDOS            equ     0005h
POS             equ     1371h           ; x (1371h), y (1372h) del texto
COLVAR          equ     15FAh           ; color actual (lo guarda 164Eh)
PR83            equ     13BAh           ; pinta el nombre 8.3 del registro HL
PRCHR           equ     15A8h           ; pinta A (>= 20h) en POS y avanza x en 3
SETCOL          equ     164Eh
GETREC          equ     36C4h
PRDATE          equ     35C3h
RECPTR          equ     3E8Ch           ; registro que esta rellenando 3E88h
FIB             equ     0C934h          ; el FIB de MM al listar
PATH            equ     5780h           ; ruta de MM: "X:\..." (PATH+3 = 0 en la raiz)
DPB             equ     5FDFh           ; el _DPARM que hace MM al leer el directorio

_SETDTA         equ     1Ah
_CURDRV         equ     19h
_FFIRST         equ     40h
_RDDRV          equ     73h
_GETCLUS        equ     7Eh

MARCA           equ     0A5h            ; registro+12 = MARCA: +13..17 = FIB+45..49
NAMEW           equ     12              ; ancho normal del campo Name (8.3)
WIDEW           equ     31              ; ancho con la fecha tapada (hasta el borde)
HEADW           equ     20              ; recortado: 20 + "..." + 8
TAILW           equ     8
LFNSEQ          equ     20              ; 20 partes x 13 = 260 caracteres
LFNSZ           equ     LFNSEQ*13+1
FRAMESZ         equ     512+LFNSZ       ; sector + nombre, en la pila
STKMIN          equ     0CCh            ; MM usa hasta CB92h: el marco no baja de CC00h

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
datestr:        db      "Date:"
dotstr:         db      ".",0
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

; pinta A espacios
spaces:         or      a
                ret     z
                ld      b,a
spc1:           ld      a,' '
                call    PRCHR
                djnz    spc1
                ret
fin3ddf:

; ================================================================ 5CF4h
                org     5CF4h

; ---------------------------------------------------------------- 34D5h
; HL = DE = registro (nombre 8.3 de 11 bytes); POS en el valor de "Name:".
; Al volver, B+C = espacios que pinta MM para acabar el campo (como 13BAh).
name:           push    ix
                push    hl
                push    de
                ld      (target),hl
                ld      a,(hl)
                cp      '.'
                jr      z,no
                ld      hl,-FRAMESZ
                add     hl,sp
                ld      a,h
                cp      STKMIN
                jr      c,no
                ld      (frame),hl
                ld      de,512
                add     hl,de
                ld      (lfnp),hl
                ld      (savesp),sp
                ld      hl,(frame)
                ld      sp,hl
                call    find            ; NC: encontrado
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

; pinta el nombre largo; vuelve NC y con BC como 13BAh
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
                ld      b,5
                call    prn
                pop     af
                call    SETCOL
                ld      a,1
                call    spaces
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
                ld      de,12
                add     hl,de
                ld      a,(hl)
                cp      MARCA
                jr      nz,full
                inc     hl
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
                ld      hl,0
                or      a
                jr      nz,f_root       ; sin "." -> raiz
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
wide            equ     fincod
expect          equ     wide+1
chk             equ     expect+1
drive           equ     chk+1
st              equ     drive+1
target          equ     st+1
frame           equ     target+2
lfnp            equ     frame+2
savesp          equ     lfnp+2
clus            equ     savesp+2
left            equ     clus+2
sect            equ     left+2
finvar          equ     sect+4
; parchear.py comprueba los limites de cada trozo
