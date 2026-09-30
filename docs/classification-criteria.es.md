# Criterios de clasificación de conversaciones

*[Read in English](classification-criteria.md)*

Documento de definiciones acordadas. Es la fuente de verdad para la implementación
del clasificador. Las cifras citadas provienen de un archivo de muestra real
(01–02/08/2026, 3.219 conversaciones); los datos de este repositorio son sintéticos.

> **Sobre la configurabilidad.** Este documento describe el esquema por defecto (la primera
> campaña para la que se construyó la herramienta). Hoy cada campaña puede definir sus propias
> categorías, indicadores y árbol de decisión (ver `analysis/schema.py`), así que las categorías
> de abajo son un ejemplo del método, no una lista fija.

---

## 1. Categorías

Cada conversación recibe **una** `categoria_final`, de estas cuatro:

| Categoría | Definición | Cómo se determina |
|---|---|---|
| `SIN_RESPUESTA` | El cliente nunca escribió. Es un mensaje masivo no contactado, **no** un rechazo. | Regla dura |
| `INTERESADO` | Declaró intención de compra o pidió avanzar con un asesor. | Regla dura |
| `RESOLVIO_DUDAS` | Solicitó información sobre producto, cupo, tasas o condiciones. | **IA** |
| `NO_INTERESADO` | Manifestó explícitamente que no está interesado. | Regla dura |

### 1.1 `SIN_RESPUESTA`

El cliente no emitió ningún mensaje (`0` mensajes con `sender = 'CUSTOMER'`).

Corresponde a los envíos proactivos masivos que nadie contestó: **3.002 de 3.219
conversaciones (93,3%)** en la muestra. Se separa explícitamente porque no encaja en
ninguna de las otras tres y, de mezclarse, distorsionaría todos los indicadores.

### 1.2 `INTERESADO`

**Criterio (revisado tras la validación manual): el cliente ADQUIRIÓ el cupo**, es
decir, concretó la solicitud. Declarar intención sin concretar **no** es suficiente.

> Palabras del cliente: *"se marca como interesado cuando la persona adquiere el cupo;
> si hace preguntas pero no adquiere el cupo, o no expresa que quiere el cupo, pues no
> es interesado, es resolvió pregunta"*.

Se registran **dos niveles**, porque responden a preguntas de negocio distintas:

| Flag | Significado | Señal | ¿Define la categoría? |
|---|---|---|---|
| `interes_declarado` | Manifestó intención inicial | Pulsó `Quiero usar mi cupo` o `Hablar con un asesor` | **No.** Solo informativo |
| `interes_confirmado` | **Concretó**: la solicitud quedó registrada y escalada a un asesor | El bot emitió `✅ Hemos registrado tu interés`, o la IA detecta que aceptó avanzar con la compra | **Sí** |

`categoria_final = INTERESADO` únicamente cuando `interes_confirmado` es verdadero.

**No** son interés confirmado (todos estos casos son reales de la muestra):

- Preguntar precios o cuotas con mucho detalle: *"estoy interesado en presentar cuatro
  millones, cuánto tengo que pagar al mes"* → es una **pregunta**, no una adquisición.
- Interés a futuro: *"más adelantico luego yo les hablo cuando esté ya mejorada"*.
- Pulsar `Quiero usar mi cupo` al inicio y abandonar la conversación.

> Nota de negocio: quienes declararon intención pero no concretaron son un indicador de
> fuga. El flag `interes_declarado` permite medirlos sin contarlos como interesados.

### 1.3 `RESOLVIO_DUDAS`  (flag: `busco_informacion`)

El cliente **obtuvo información** sobre el producto, el cupo, las tasas, las
condiciones, los aliados o los puntos de venta.

**Criterio acordado (ampliado tras la validación manual): cuenta tanto si preguntó
explícitamente como si obtuvo la información avanzando en el flujo guiado del bot.**
Por eso el flag se llama `busco_informacion` y no `hizo_preguntas`: exigir una
pregunta formal dejaba fuera casos en los que el cliente sí resolvió una duda.

Tampoco se exige que el bot haya respondido bien — la categoría mide lo que buscaba
el cliente, no el desempeño del bot. Los fallos del bot van aparte en `bot_no_resolvio`.

**Incluye** (ejemplos reales de la muestra; ninguno lleva signo `?`):

```
Preguntas explícitas:
  "Que intereses manejan"      "Cuanto es mi cupo"
  "Los intereses"              "A qué puntaje es el interés"

Información obtenida sin preguntar, dentro del flujo guiado:
  "Un televisor" → "Tienda Central o ElectroHogar" → el bot le indica con qué aliados comprarlo
  "Efectivo"     → el bot le aclara que el cupo no entrega dinero en efectivo
```

**Excluye explícitamente:**

- Saludos: `"Hola"`, `"Buenos días"`, `"Buen día"`
- Agradecimientos y cierres de cortesía: `"Gracias"`, `"Muchas gracias"`, `"Ok"`
- Respuestas a la encuesta de rechazo (ver 1.4)
- Los botones de menú (`Quiero usar mi cupo`, etc.), que son intención, no consulta
- Todo lo que diga el **bot**: el bot pregunta constantemente (*"¿tienes algún producto
  en mente?"*), y esas preguntas no son del cliente

**Por qué esta categoría requiere IA:** solo el **6%** de los clientes usa signo de
interrogación, frente a un **48%** que escribe texto libre sin él. Una detección por
expresiones regulares basada en `?` capturaría alrededor de 14 de las ~70 preguntas
reales. Y no se resuelve ampliando patrones: `"Los intereses"` es sintácticamente
indistinguible de un comentario suelto — lo que la convierte en pregunta es el
contexto conversacional.

### 1.4 `NO_INTERESADO`

Rechazo explícito. Señales:

- El cliente pulsó el botón `No estoy interesado` (112 apariciones exactas), **o**
- El bot emitió la encuesta de motivos: `Lamentamos que por ahora no desees...`

Las respuestas a esa encuesta (dígitos `1`–`6`, correspondientes a *1️⃣ No necesito
comprar*, … *6️⃣ Tuve una mala experiencia*) se tratan como **parte del mismo evento de
rechazo**, nunca como preguntas.

`NO_INTERESADO` es además la categoría por defecto: si el cliente respondió pero no
concretó la adquisición ni preguntó nada, no es un interesado. Esto incluye a quienes
solo saludaron o agradecieron, y a los autorespondedores de empresas (ver 1.5).

### 1.5 Autorespondedores de empresas (`es_autorespondedor`)

Parte de los números de la base de campaña **no pertenecen a personas sino a negocios**,
cuyo autorespondedor de WhatsApp contesta al bot. Ejemplos reales:

```
"Gracias por comunicarte con Consultorio Dental Sonrisas. ¿Cómo podemos ayudarte?"
"¡Bienvenid@ a Ferretería El Tornillo. ¿Como podemos ayudarte?"
"...recuerda que nuestro horario administrativo es de 7:30 a 4:00 pm"
```

Ese *"¿Cómo podemos ayudarte?"* se confundía con una pregunta del cliente e inflaba
`RESOLVIO_DUDAS`. Ahora se detectan por regla, se clasifican como `NO_INTERESADO` y se
marcan con el flag `es_autorespondedor`.

**Valor de negocio:** el flag permite listar los contactos que hay que depurar de la
base de campaña, porque nunca van a convertir.

> **Cuidado — el autorespondedor no siempre significa que no haya nadie.** Se detectó
> un caso real en el que la empresa autorrespondió y **después una persona siguió
> escribiendo** (pidió el catálogo y preguntó por un avance en efectivo). Por eso la
> regla solo clasifica directamente cuando el autorespondedor es lo **único** que hay;
> si queda cualquier otro texto del cliente, la conversación pasa a la IA y las señales
> de esa persona se evalúan con normalidad. El flag marca al **contacto**, no anula el
> análisis.

---

## 2. Jerarquía

Cuando aplica más de una categoría:

```
INTERESADO  >  RESOLVIO_DUDAS  >  NO_INTERESADO
```

Ejemplos:
- Preguntó y luego declaró interés → `INTERESADO`
- Preguntó y luego rechazó → `RESOLVIO_DUDAS`
- Solo rechazó → `NO_INTERESADO`

### 2.0 Las señales son independientes entre sí

Una señal **no cancela** a otra: se evalúan por separado sobre toda la conversación.
En particular, **que el cliente rechace al final no borra la información que obtuvo
antes**.

Caso real que obligó a explicitarlo: el cliente pide `"Efectivo"`, el bot le aclara
que el cupo no entrega dinero en efectivo, y el cliente responde `"No, gracias"`.

```
busco_informacion  = true   (sí obtuvo la aclaración)
rechazo_explicito  = true   (sí dijo que no)
categoria_final    = RESOLVIO_DUDAS   (por jerarquía)
```

El modelo tendía a elegir una sola señal y descartar la otra; el prompt ahora lo
prohíbe de forma explícita.

### 2.1 Se conservan las señales individuales

La categoría única simplifica el reporte, pero **pierde información**: los 112 rechazos
explícitos quedarían diluidos. Por eso se almacenan también los flags independientes:

```
interes_declarado    true/false     (intención inicial; NO define la categoría)
interes_confirmado   true/false     ← define INTERESADO
busco_informacion    true/false     ← define RESOLVIO_DUDAS
rechazo_explicito    true/false
bot_no_resolvio      true/false     (calidad del bot, no clasifica)
es_autorespondedor   true/false     (contacto a depurar, no clasifica)
categoria_final      <derivada de la jerarquía>
```

Esto permite responder sin reprocesar nada preguntas como *"¿cuántos de los que
preguntaron terminaron rechazando?"* o *"¿cuántas veces el bot no supo responder?"*.

---

## 3. Cascada de clasificación

El orden importa: la jerarquía permite cortar temprano. Como `INTERESADO` gana siempre,
al detectarlo por regla dura **ya no hace falta averiguar si además preguntó**, lo que
evita enviar esas conversaciones a la IA.

| Capa | Criterio | Método | Convs | % del universo con respuesta |
|---|---|---|---|---|
| 0 | Sin mensajes del cliente | Regla dura | 3.002 | — |
| 1 | `INTERESADO` | Regla dura | 71 | 33% |
| 2 | `NO_INTERESADO` sin otra interacción | Regla dura | 69 | 32% |
| 3 | Zona gris | **IA** | 77 | 35% |

**La IA solo procesa 77 de 3.219 conversaciones (2,4%).**

### 3.1 Por qué reglas y no IA para las capas 0–2

El argumento principal **no es el costo** (a este volumen sería mínimo de cualquier
forma), sino la **auditabilidad**: una regla determinística siempre produce el mismo
resultado y permite explicar exactamente por qué una conversación quedó en cierta
categoría. La IA no es determinística y no ofrece esa garantía.

Las señales usadas en las capas 1 y 2 son fiables porque **no dependen de texto escrito
libremente por el cliente**:

- **Plantillas del bot**: generadas por máquina, texto idéntico siempre.
- **Botones de menú**: el cliente los *pulsa*, no los escribe, y llegan con texto exacto
  (`No estoy interesado` aparece 112 veces carácter por carácter).

Aplicar expresiones regulares al texto libre del cliente sería frágil: la muestra real
contiene `"Dodne. Averiguo"`, `"No. Yo voy. Almscen"`, `"Homcenter."` — con errores
ortográficos, sin tildes y sin puntuación.

---

## 4. Validación

La clasificación automática se contrasta contra etiquetado manual **a ciegas** (sin
mostrar la respuesta de la IA, para no anclar el criterio humano):

```bash
python scripts/validar_ia.py --exportar validacion.xlsx   # exporta sin la respuesta de la IA
# ... se llena la columna TU_CATEGORIA ...
python scripts/validar_ia.py --comparar validacion.xlsx   # mide acuerdo y lista desacuerdos
```

### 4.1 Resultado de la primera validación

La primera ronda dio **60% de acuerdo (30/50)**. Analizar los 20 desacuerdos no fue un
trámite: reveló cuatro problemas reales, y todas las definiciones de este documento
marcadas como "revisado" o "ampliado" salieron de ahí:

| Causa | Casos | Corrección aplicada |
|---|---|---|
| `INTERESADO` demasiado amplio | 7 | Ahora exige `interes_confirmado` (adquirir, no solo declarar) |
| Autorespondedores de empresas | 6 | Detección por regla + flag `es_autorespondedor` (§1.5) |
| `SIN_CLASIFICAR` sobraba | 5 | Eliminada; el caso cae en `NO_INTERESADO` |
| `RESOLVIO_DUDAS` demasiado estrecho | 2 | Ampliado a "obtuvo información" (§1.3) |

Además la validación dejó al descubierto cuatro errores propios:

1. **El prompt contaba las preguntas del bot** como si fueran del cliente. Corregido con
   una instrucción explícita al inicio (§ REGLA 1 del prompt).
2. **El modelo trataba las señales como excluyentes**: un rechazo al final borraba la
   información obtenida antes. Corregido en §2.0.
3. **La regla de autorespondedor cortaba demasiado pronto**, asumiendo que si contestaba
   un bot de empresa no había ninguna persona detrás. Corregido en §1.5.
4. **El modelo sobre-marcaba `es_autorespondedor`**: llegó a marcar como "empresa" a
   clientes que solo habían pulsado *"Quiero usar mi cupo"*, confundiendo *"el Bot es
   automático"* (siempre lo es, es el chatbot de la empresa) con *"el número del cliente es
   de una empresa"*. Tras dos intentos de afinar el prompt sin lograr precisión, se
   **quitó esa señal de la IA por completo**: hoy `es_autorespondedor` lo determinan
   solo las reglas.

   Es una aplicación del principio de la §3.1: los autorespondedores son **texto
   corporativo con plantilla fija**, exactamente lo que las reglas resuelven bien.
   Pedírselo al modelo fue un error de diseño. Además el costo de equivocarse es
   asimétrico — un falso positivo marca para depuración el número de un cliente real,
   mientras que un falso negativo solo hace que la conversación se clasifique con
   normalidad. Por eso se prioriza precisión sobre cobertura, y la lista de patrones
   se amplía cuando aparezcan formatos nuevos.

   Se detectó al auditar el propio flag antes de reportarlo como métrica de negocio,
   no por una prueba automática: conviene revisar por muestreo cualquier señal nueva
   antes de darla por buena.

### 4.2 Segunda ronda

Con esas correcciones, 18 de los 20 desacuerdos originales quedaron resueltos. Los dos
restantes los revisó el usuario uno por uno y ambos resultaron ser defectos reales del
clasificador (puntos 2 y 3 de arriba), no diferencias de criterio.

**Lección de método:** la validación ciega no sirvió para "aprobar" el clasificador sino
para descubrir que las definiciones escritas no coincidían con el criterio real del
negocio. Conviene repetirla cada vez que cambien los criterios o el archivo de origen.
