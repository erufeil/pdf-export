# Generar el orden secuencial de migracion de tablas SQL

## Nombre del boton para index.html
                        <div class="card-icon">NDM</div>
                        <h3>Migrar SQL</h3>
                        <p>Ordenar Tablas p/export</p>

## Objetivo
Debe generar el orden secuencial de migracion de tablas de bases de datos SQL teniendo en cuenta las PK y FK.
Teniendo: una tabla A: pk y otra tabla B: pk y fk_tabla_A. Como la fk_tabla_A es foranea en tabla B la tabla A debe ir primero y tabla B segunda por que tabla B depende de tabla A.

## Estructura del archivo fuente
Formato: Navicat Data Modeler (versión 2), JSON
Fuente: ArchivoUploaded.ndm2

## Mapa de rutas del JSON
El archivo .ndm2 tiene esta jerarquía (simplificada):
json_ndm = importar-json("ArchivoUploaded.ndm2")

json_ndm                              ← raíz del archivo
├── server
│   └── schemas[]                     ← lista de esquemas (usamos el primero)
│       ├── name                      ← nombre de la base de datos
│       └── tables[]                  ← lista de tablas (se recorre completa)
│           ├── name                  ← nombre de la tabla
│           └── foreignKeys[]         ← lista de FKs (puede estar vacía)
│               ├── referenceSchema   ← base de datos de la tabla referenciada
│               └── referenceTable    ← nombre de la tabla referenciada

Acceso en Python:

esquema           = json_ndm["server"]["schemas"][0]
nombre_db         = esquema["name"]                        → "MASVIDADIGNA"
lista_tablas      = esquema["tables"]                      → [tabla1, tabla2, ...]
  ┗ por cada tabla en lista_tablas:
      nombre_tabla  = tabla["name"]                        → "T_USUARIOS"
      lista_fks     = tabla["foreignKeys"]                 → [{fk1}, {fk2}] o []
        ┗ por cada fk en lista_fks:
            db_fk     = fk["referenceSchema"]              → "MASVIDADIGNA"
            tabla_fk  = fk["referenceTable"]               → "T_INSCRIPCIONES_MVD"

## Logica de programacion

**Página:** `static/ndm-to-tables-seq.html`
**Descripción:** Analiza archivo ndm2 y devuelve secuencia logica de migracion de tablas.
**Endpoint:** `POST /api/v1/convert/ndm-to-tables-seq`
**Parámetros:**
```json
{
    "file_id": "uuid-del-archivo",
    "opciones": {
        "formato_salida": "original",
        "sin_comprimir": true
    }
}
```
 
1. importa el json y define variables: nombre_db_principal_json, orden_de_migracion, notas_al_pie, control_cambios=0, max_iteraciones = 1000
2. extrae los nombres de las tablas
3. ordena segun algoritmo
4. devolver archivo .TXT en texto plano compatible con notepad de windows

## Algoritmo:

### Extraccion y 1er orden: sin FK primero con FK despues
Extrae el nombre de la tabla de json_ndm["server"]["schemas"]["name"] en la variable nombre_db_principal_json.
Recorre la clave json_ndm["server"]["schemas"]["tables"]["name"] y json_ndm["server"]["schemas"]["tables"]["foreignKeys"] de cada "tables" extrayendo el valor de cada clave en las variables nombre_tabla_json y fk_tabla_json respectivamente. 
En cada iteración arma una lista llamada orden_de_migracion con los nombres de las tablas pero antes revisa: si fk_tabla_json == [] entonces agrega nombre_tabla_json al comienzo de orden_de_migracion, caso contrario al final.
max_iteraciones = len(orden_de_migracion)

## Orden de prioridad

1. Recorre la lista orden_de_migracion de principio a fin, extrayendo cada
   elemento en nombre_tabla_lista y su posición en posicion_tabla_lista.

2. Para cada nombre_tabla_lista, busca su entrada correspondiente en el JSON
   (donde nombre_tabla_json == nombre_tabla_lista) y extrae fk_tabla_json.

   2.1. Si fk_tabla_json == [] (sin foreign keys), pasa al siguiente elemento
        de orden_de_migracion.

   2.2. Si tiene foreign keys, recorre cada FK dentro de fk_tabla_json
        extrayendo "referenceSchema" en db_tabla_fk y "referenceTable"
        en tabla_fk.

        2.2.a. Si db_tabla_fk != nombre_db_principal_json, agrega en
               notas_al_pie: 'WARNING: {tabla_fk} pertenece a la base
               de datos {db_tabla_fk}' y continúa con punto 2.2.b.

        2.2.b. Busca la posición de tabla_fk en orden_de_migracion y
               la guarda en posicion_tabla_fk.
               Si posicion_tabla_fk > posicion_tabla_lista entonces:
               borra nombre_tabla_lista de orden_de_migracion, lo inserta
               en posicion_tabla_fk y marca control_cambios = 1.
               Caso contrario, continúa.

   2.3. Una vez recorridas todas las FK de este elemento, pasa al siguiente
        elemento de orden_de_migracion.

3. Una vez recorrida toda la lista, evalúa control_cambios:

   3.1. Si control_cambios == 0, termina y continúa con la devolución
        de la lista.

   3.2. Si control_cambios == 1:
        iteraciones += 1
        Si iteraciones >= max_iteraciones, agrega en notas_al_pie:
        'WARNING: Posible dependencia circular detectada' y termina.
        Caso contrario, coloca control_cambios = 0 y vuelve al paso 1.

## Formato del archivo a devolver:
Nombre: 'Orden_secuencial_migracion_SQL_ERF.txt'
Formato: texto plano para notepad de windows
Presentacion:
Titulo: Orden migracion de {nombre_db_principal_json}
Cuerpo: orden_de_migracion en formato de lista:
1. Tabla1
2. Tabla2
3. Tabla3
...
Pie del documento: notas_al_pie

### Nota de la IA: 
El algoritmo es un "Topological Sort". Lo que describís es esencialmente un ordenamiento topológico de un grafo dirigido (tablas = nodos, FK = aristas). Python tiene graphlib.TopologicalSorter desde Python 3.9 que hace exactamente esto y detecta ciclos automáticamente. Libreria que no usaremos e implementaremos este algoritmo.

