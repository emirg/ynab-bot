# Roadmap — YNAB Telegram Bot

Short-term roadmap (Q2 2026). Three milestones ordered by impact: fix what frustrates today, add the most requested feature, then polish the overall experience.

## Milestone 1: Onboarding & Learning Transparente

### 1.1 — Guided Onboarding Flow [COMPLETADO]

Hoy un usuario nuevo que hace `/start` no sabe qué hacer después. La mejora es un flujo guiado:

- Mensaje de bienvenida que explica qué hace el bot
- Detectar si el usuario ya conectó YNAB; si no → guiar a `/connect`
- Post-OAuth → guiar automáticamente a seleccionar budget y account
- Al completar configuración → enviar ejemplo: "Ahora probá enviando algo como: almuerzo 25000"
- Agregar `/help` con resumen de comandos disponibles

### 1.2 — Learning Dashboard

Nuevo comando `/aprendizaje` que muestra qué ha aprendido el bot del usuario:

- Lista de asociaciones payee → categoría con frecuencia ("McDonald's → Restaurantes (7 veces)")
- Comando `/olvidar <payee>` para eliminar asociaciones incorrectas
- Mejorar `/stats` con información más accionable

### 1.3 — Explicación de Decisiones

Cuando el bot registra un gasto, incluir en la respuesta por qué eligió esa categoría:

- "Categoría: Restaurantes (aprendido de tus últimas 5 compras en McDonald's)"
- "Categoría: Groceries (sugerido por IA, confianza 85%)"
- Una línea extra en la respuesta, breve y no invasiva

## Milestone 2: Gastos Compartidos (Split)

### 2.1 — Split Transaction Support

Registrar gastos compartidos que se dividen en dos categorías YNAB usando subtransactions:

- Una parte va a la categoría "Splitwise" (o como el usuario la tenga en YNAB)
- La otra parte va a la categoría real del presupuesto
- Ejemplo: "almuerzo compartido 50000 restaurantes" → split 25000 Splitwise + 25000 Restaurantes
- El usuario debe ser capaz de registrar gastos que hizo la otra persona en su nombre. Por ejemplo, "Juan compró un almuerzo por 50000 en restaurantes" → split 25000 Splitwise + 25000 Restaurantes". Eso debe ir a una cuenta "Shared Transactions" en YNAB.

### 2.2 — Configuración de Split

- Comando `/splitwise` para configurar cuál es la categoría Splitwise del usuario (una sola vez, se persiste)
- El usuario puede tener varias categorías Splitwise (por ejemplo, una para cada persona con la que divide gastos)
- División por defecto: 50/50
- Soporte para proporciones ("compartido 60000 restaurantes 2/3") o monto fijo ("compartido 60000 restaurantes mi parte 20000")

### 2.3 — Detección de Intent en LLM Parser

- Palabras clave como "compartido", "split", "mitad" activan el intent `shared_expense`
- El LLM parser extrae: monto total, categoría, y proporción si la hay
- Respuesta clara mostrando el desglose: "Registrado: Almuerzo $50.000 → Splitwise $25.000 + Restaurantes $25.000"

## Milestone 3: Robustez & Calidad de Vida

### 3.1 — Editar/Eliminar Último Gasto

- `/deshacer` — elimina la última transacción creada en YNAB
- `/editar` — corregir monto, categoría o payee del último gasto
- Ventana de tiempo razonable (últimos 5 minutos o última transacción del día)

### 3.2 — Confirmación Opcional Pre-Registro

- Modo configurable por usuario: antes de crear la transacción, el bot muestra un preview y espera confirmación
- "Voy a registrar: Almuerzo $25.000 en Restaurantes. ¿Confirmar?"
- Activable/desactivable via `/confirmacion on/off`
- Por defecto desactivado para no agregar fricción

### 3.3 — Mejor Manejo de Errores

- Mensajes de error más claros y accionables en español
- Reintentos automáticos para errores transitorios de la API de YNAB (429, 500)
- Logging estructurado para diagnóstico

### 3.4 — Resumen Periódico

- Comando `/resumen` — resumen de gastos del día/semana/mes actual
- Desglose por categoría con totales
- Comparación contra lo presupuestado si está disponible via YNAB API

### 3.5 — Alertas

- TODO
