# Conciliador de ingresos – Las Perdices

Automatiza los pasos 1 a 3 del registro de ingresos del condominio:

1. Lee los ingresos de la cartola detallada de la cuenta corriente.
2. Registra ID interno, fecha, monto y nombre en orden cronológico.
3. Asigna cada pago a su depto y lo ubica en la fila correspondiente de la hoja del período.

El paso 4 (ingreso en Comunidad Feliz) sigue siendo manual y se hace a partir del Excel generado.

Todo corre en tu computador: los archivos no salen de él.

---

## Uso desde la web (Streamlit Community Cloud)

La app se despliega desde este repositorio de GitHub y se abre desde cualquier navegador.

**Despliegue (una sola vez):**

1. Entra a https://share.streamlit.io e inicia sesión con tu cuenta de GitHub.
2. *Create app* → *Deploy a public app from GitHub* y elige:
   - Repository: `Estay36/conciliador-perdices`
   - Branch: `main`
   - Main file path: `app.py`
3. En *Advanced settings*, elige Python 3.12 y presiona *Deploy*.
4. Una vez desplegada, en *Settings → Sharing* deja la app como **privada** e invita solo
   los correos que deben usarla. La app procesa nombres, RUT y montos de los residentes.

Cada `git push` a `main` actualiza la app automáticamente.

**Privacidad:** el repositorio no contiene datos del condominio (el `.gitignore` excluye
todo `.xlsx` y `.csv`). Los archivos se cargan en cada sesión y no quedan guardados en el servidor.

**Diccionario de pagadores en la web:** el disco de Streamlit Cloud no es persistente.
Al final de cada corrida, descarga `diccionario_pagadores.csv` y vuelve a cargarlo en la
siguiente (tercer recuadro de carga). Así el sistema sigue aprendiendo RUT → depto.

## Uso local (alternativa sin internet)

1. Instala Python 3.10 o superior desde https://www.python.org/downloads/
   (en Windows, marca **"Add python.exe to PATH"**).
2. Clona o descarga este repositorio.
3. Doble clic en `Conciliar.bat` (Windows) o `Conciliar.command` (Mac). La primera vez instala
   las dependencias; luego abre el navegador. En modo local el diccionario se guarda solo en
   `datos/diccionario_pagadores.csv`.

## Uso mensual / semanal

1. Descarga la cartola detallada desde el banco (`Movimientos_Detallado_Cuenta_...xlsx`).
2. Abre la aplicación (URL de Streamlit o lanzador local).
3. Carga la **cartola**, la **planilla madre** (`Ingresos_Las_Perdices.xlsx`) y, si lo tienes,
   el **diccionario de pagadores** de la corrida anterior.
4. Elige la **hoja a rellenar** (ej. `Oct26`). El sufijo del ID se infiere del nombre (`1026`).
5. Revisa el **último pago ya registrado**: la app lo sugiere automáticamente (el pago más
   reciente de la hoja anterior, o de la misma hoja si ya tiene ingresos). Puedes cambiarlo
   eligiendo otro movimiento de la lista.
6. Si la hoja del período ya terminó (por ejemplo, Oct26 cubre hasta ~10/11), marca
   **Limitar hasta una fecha** para no cargar pagos del período siguiente en esa hoja.
7. Presiona **Conciliar** y descarga el Excel (y el diccionario actualizado).

**Montos como número:** al pegar en la planilla madre, usa *Pegado especial → Valores* desde
el Excel de salida. Si los montos quedan como texto (`$141.245`), las fórmulas `SUMA` de la
hoja no los consideran. La app los lee igual, pero los totales de la planilla quedan mal.

### Qué contiene el Excel de salida

| Hoja | Contenido |
|---|---|
| `Oct26` (nombre de la hoja elegida) | Copia exacta de la hoja de la planilla madre con los bloques **A:F (por depto)** e **I:M (cronológico)** rellenados. Misma estructura y mismas filas: se copia y pega directamente en la planilla madre. |
| `Revisión` | Una fila por ingreso: datos de la cartola (RUT, comentario, código), depto asignado, **confianza**, método y observaciones. Tiene filtros. |
| `Resumen` | Totales, período procesado, pendientes y alertas. |

**Para pegar en la planilla madre:** selecciona `B5:F179` y `I5:L…` en la salida y pégalos en
las mismas celdas de la hoja del período. Si no quieres traspasar los colores de revisión,
usa *Pegado especial → Valores* (o desmarca "Colorear" antes de conciliar).

### Cómo leer la confianza

| Confianza | Significado | Acción |
|---|---|---|
| ALTA (sin color) | Comentario con N° de depto, RUT conocido o nombre con historial consistente. | Ninguna. |
| MEDIA (amarillo) | Hay una señal clara pero con alguna discrepancia (ej. el comentario indica un depto y el nombre otro). La columna F dice `REVISAR: …`. | Verificar. |
| BAJA (naranjo) | El nombre calza igual de bien con más de un depto. | Verificar y mover si corresponde. |
| SIN MATCH (rojo en el cronológico) | Pagador nuevo sin comentario útil. Queda solo en el bloque cronológico con `Encontrado = No`. | Asignar a mano. |

### Reglas de negocio incorporadas

- **$40.000 = reserva de quincho**: va a las filas `Arriendo quincho` de la sección OTROS.
  Si el comentario no menciona reserva/garantía/salón, se marca MEDIA para revisión.
- **Pagos de Comunidad Feliz** (`PAGO_MASIVO`): se registran en el bloque cronológico como
  "Comunidad Feliz" y no se asignan a depto (ya quedan imputados en CF).
- **Nombres inconsistentes**: la comparación ignora tildes, mayúsculas, orden de nombres y
  apellidos ("MORA RIOSECO KARINA" = "Karina Mora Rioseco"), segundos nombres, nombres
  truncados por el banco ("Gabriela Alejandra Val") y errores menores ("Gonzales"/"Gonzalez").
- **Nombre escrito en la planilla**: se usa el mismo nombre con que ese pagador ya aparece
  en meses anteriores, para mantener consistencia.
- **Comentarios**: se reconocen "depto 415", "Dpto.1716", "Dp718", "dpto 1413 torre 2"
  (→ `1413 T2`), "estacionamiento 287" (→ `BX 287 - BD 248`), etc.
- **Duplicados**: si un ingreso nuevo coincide en fecha y monto con uno ya registrado en
  otra hoja, se alerta.
- **Depto sin fila libre**: si un depto recibe más pagos que filas disponibles, el pago queda
  en el cronológico y se alerta para insertar una fila en la planilla madre.

### Diccionario de pagadores (`datos/diccionario_pagadores.csv`)

Cada corrida agrega los pares **RUT → depto** asignados con confianza ALTA. El RUT es la señal
más confiable, así que con el tiempo casi todo se resuelve automáticamente. Se puede editar
en Excel (separador `;`): para corregir una asociación, cambia el depto o borra la fila.
Si un RUT paga dos deptos, deja una fila por cada uno.

---

## Uso por línea de comandos (opcional)

```bash
python conciliar.py --cartola cartola.xlsx --madre Ingresos_Las_Perdices.xlsx --hoja Oct26 \
    --ultimo-fecha 10/10/2026 --ultimo-monto 120645 --ultimo-nombre "María Cecilia Salazar"
```

Si se omiten `--ultimo-*`, se usa el último pago sugerido desde la planilla.
Otras opciones: `--hasta`, `--sufijo-id`, `--id-inicial`, `--salida`, `--sin-colores`.

## Estructura del código

```
conciliador/
  config.py         Parámetros: monto quincho, columnas de la cartola, layout de la planilla
  normalizacion.py  Limpieza de textos/RUT y comparación de nombres
  cartola.py        Lectura de la cartola y selección del período
  planilla.py       Lectura de la hoja objetivo, historial, Datos Residentes y Encontrados
  matching.py       Reglas de asignación (comentario → RUT → nombre)
  diccionario.py    Diccionario persistente RUT → depto
  salida.py         Escritura del Excel (hoja del período, Revisión, Resumen)
  pipeline.py       Orquestación de una corrida
app.py              Interfaz web/local (Streamlit)
conciliar.py        Línea de comandos
tests/              Pruebas (python -m pytest)
```

Si el banco cambia los nombres de columna de la cartola, o la planilla cambia de columnas,
basta con ajustar `conciliador/config.py`.
