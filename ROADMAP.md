# Roadmap — YNAB Telegram Bot

Short-term roadmap (Q2 2026). Three milestones ordered by impact: fix what frustrates today, add the most requested feature, then polish the overall experience. Features implemented outside of the original roadmap are tracked in the "Extras" section.

## Milestone 1: Onboarding & Learning Transparente [COMPLETADO]

### 1.1 — Guided Onboarding Flow [COMPLETADO]

Hoy un usuario nuevo que hace `/start` no sabe qué hacer después. La mejora es un flujo guiado:

- Mensaje de bienvenida que explica qué hace el bot
- Detectar si el usuario ya conectó YNAB; si no → guiar a `/connect`
- Post-OAuth → guiar automáticamente a seleccionar budget y account
- Al completar configuración → enviar ejemplo: "Ahora probá enviando algo como: almuerzo 25000"
- Agregar `/help` con resumen de comandos disponibles

### 1.2 — Learning Dashboard [COMPLETADO]

Nuevo comando `/aprendizaje` que muestra qué ha aprendido el bot del usuario:

- Lista de asociaciones payee → categoría con frecuencia ("McDonald's → Restaurantes (7 veces)")
- Comando `/olvidar <payee>` para eliminar asociaciones incorrectas
- Mejorar `/stats` con información más accionable

### 1.3 — Explicación de Decisiones [COMPLETADO]

Cuando el bot registra un gasto, incluir en la respuesta por qué eligió esa categoría:

- "Categoría: Restaurantes (aprendido de tus últimas 5 compras en McDonald's)"
- "Categoría: Groceries (sugerido por IA, confianza 85%)"
- Una línea extra en la respuesta, breve y no invasiva

## Milestone 2: Gastos Compartidos (Split) [COMPLETADO]

### 2.1 — Configuración de Split [COMPLETADO]

- Comando `/splitwise` para configurar cuál es la categoría Splitwise del usuario (una sola vez, se persiste)
- El usuario puede tener varias categorías Splitwise (por ejemplo, una para cada persona con la que divide gastos)
- El usuario también configura cuál es su cuenta "Shared Transactions" en YNAB (para gastos pagados por otra persona en su nombre)
- División por defecto: 50/50
- Soporte para proporciones ("compartido 60000 restaurantes 2/3") o monto fijo ("compartido 60000 restaurantes mi parte 20000")

### 2.2 — Split Transaction Parsing & Creation [COMPLETADO]

Esta etapa unifica la detección del intento de gasto compartido (intent) y la creación de sus correspondientes sub-transacciones en YNAB:

- **Detección de Intent**: Palabras clave como "compartido", "split", "mitad" activan el intent `shared_expense`.
- **Extracción de Datos**: El LLM parser extrae el monto total, categoría, proporción (ej. mitad, 2/3) y nombre de la persona si aplica.
- **Creación de Subtransactions**: Registrar el gasto estructurado dividido en dos o más sub-categorías en YNAB.
  - Una parte va a la categoría "Splitwise" del grupo correspondiente.
  - La otra parte va a la categoría real del presupuesto (ej. Restaurantes).
- **Respuesta UI**: Mostrar un desglose claro: "Registrado: Almuerzo $50.000 → Splitwise $25.000 + Restaurantes $25.000".

### 2.3 - Third-Party Paid Shared Expenses [COMPLETADO]

Soportar gastos compartidos que hizo otra persona en nombre del usuario:
- **Zero-Sum Transaction**: La transacción en YNAB se registra con un saldo total de $0.
- **Flujo**: Restar monto de la categoría real del presupuesto (outflow) e incrementar la categoría Splitwise de la persona (inflow).
- **Ejemplo**: "Juan compró un almuerzo por 50000 en restaurantes" → Tu deuda ($25.000) entra a la categoría Restaurantes, y Juan te "presta" los $25.000 (Inflow en categoría Splitwise).
- Esto debe registrarse usando la cuenta "Shared Transactions" tracking account configurada en la etapa 2.1.

## Milestone 3: Robustez & Calidad de Vida [COMPLETADO]

### 3.1 — Editar/Eliminar Último Gasto [COMPLETADO]

- `/deshacer` — elimina la última transacción creada en YNAB, decrementa aprendizaje y limpia recent_transactions [COMPLETADO]
- `/editar` — corregir monto, comercio, categoría y/o cuenta de transacciones recientes. Acepta un índice opcional como primer argumento (por defecto la última). Absorbe la funcionalidad de `/corregir`: al editar la categoría, actualiza el aprendizaje payee → categoría. [COMPLETADO]
- `/corregir` — REMOVIDO, absorbido por `/editar categoria`
- Ventana de tiempo: últimos 5 minutos o última transacción del día

### 3.2 — Confirmación Opcional Pre-Registro [COMPLETADO]

- Modo configurable por usuario: antes de crear la transacción, el bot muestra un preview y espera confirmación [COMPLETADO]
- "Voy a registrar: Almuerzo $25.000 en Restaurantes. ¿Confirmar?" con botones inline [COMPLETADO]
- Activable/desactivable via `/confirmacion on/off` [COMPLETADO]
- Por defecto desactivado para no agregar fricción
- Pipeline dividido en prepare + commit para soportar la confirmación sin romper el flujo existente

### 3.3 — Mejor Manejo de Errores [COMPLETADO]

- Mensajes de error más claros y accionables en español
- Reintentos automáticos para errores transitorios de la API de YNAB (429, 500)
- Logging estructurado para diagnóstico

### 3.4 — Resumen Semanal Automático [COMPLETADO]

Cada lunes a las 8am (en la zona horaria del usuario), el bot envía automáticamente un resumen de la semana anterior:

- Total gastado en la semana
- Top 3 categorías con montos
- Comparación porcentual vs semana anterior
- Mensaje amigable si no hubo transacciones
- Job robusto con aislamiento per-user y deduplicación via `last_weekly_summary_sent`
- Tick cada 15 minutos, verifica zona horaria de cada usuario

### 3.5 — Resumen On-Demand [COMPLETADO]

- Comando `/resumen` — resumen de gastos del día/semana/mes actual
- Desglose por categoría con totales
- Comparación contra lo presupuestado si está disponible via YNAB API

## Extras (features implementadas fuera del roadmap original)

### E.1 — Análisis de Imágenes de Recibos [COMPLETADO]

Enviar una foto de un recibo al bot para registrar el gasto automáticamente:

- Procesamiento de imagen via LLM para extraer monto, payee y categoría
- Soporte para fotos directas y archivos de imagen
- Mismo flujo de registro que un gasto por texto

### E.2 — Fuzzy Payee Matching [COMPLETADO]

Al registrar un gasto, el bot busca payees existentes en YNAB y reutiliza el más parecido:

- Matching difuso contra payees existentes del usuario en YNAB
- Evita duplicación de payees con variaciones menores de nombre

### E.3 — Soporte de Fechas Específicas [COMPLETADO]

Registrar gastos con fechas pasadas o futuras en lenguaje natural:

- "almuerzo 25000 ayer", "nafta 40000 el viernes"
- Parsing de fechas relativas y absolutas via LLM

### E.4 — Configuración de Zona Horaria [COMPLETADO]

Cada usuario puede configurar su zona horaria para que las fechas y el resumen semanal se calculen correctamente:

- Comando `/timezone` para configurar zona horaria
- Se usa para determinar "hoy" al registrar gastos y para el resumen semanal

### E.5 — Consultas de Presupuesto en Lenguaje Natural [COMPLETADO]

Consultar información del presupuesto YNAB con preguntas en lenguaje natural:

- Saldo de categorías, cuentas y resumen general del presupuesto
- Intent detection via LLM para distinguir entre registro de gastos y consultas

### E.6 — Financial Advisor Phase 1 Foundations [COMPLETADO]

Se completó la base técnica para el futuro advisor web sin romper el bot actual:

- Persistencia runtime migrada de SQLite a PostgreSQL
- Runbook documentado para cutover y rollback en Railway
- El servidor HTTP público actual sigue siendo el entrypoint protegido
- El endpoint autenticado de gastos HTTP y los flujos de Telegram siguen funcionando sobre la nueva base

### E.7 — Financial Advisor Phase 2 Access/Auth [COMPLETADO]

Se completó la primera entrada autenticada al advisor web sobre la base PostgreSQL:

- Comando `/analisis` desde Telegram para abrir el advisor
- Link one-time de acceso emitido desde Telegram
- Sesión por usuario en servidor con cookie HTTP-only
- Landing page autenticada del advisor
- Bootstrap/logout del advisor en el mismo servidor HTTP público actual

### E.8 — Financial Advisor Phase 4 Insights [COMPLETADO]

Se completó la primera capa de insights determinísticos sobre el dashboard del advisor:

- Insights read-only dentro de `/advisor` sobre el dashboard existente
- Alertas por concentración de gasto y ritmo mensual proyectado
- Señales de categorías sobregastadas o cerca del límite
- Detección de categorías con presupuesto asignado pero sin actividad
- Estado explícito de "sin alertas fuertes" cuando no aparecen señales relevantes

### E.9 — Voice Transcription Hardening [COMPLETADO]

Se corrigió una regresión crítica donde los audios podían producir una transcripción ajena como `Mas informacion www.alimmenta.com`:

- La ruta de voz valida transcripciones antes de pasarlas al parser de gastos
- Se rechazan textos dominados por URLs, dominios o boilerplate conocido
- Los errores de voz siguen siendo seguros y en español
- El logging evita guardar audio o transcripciones completas

### E.10 — Recent Edit Reconciliation Hardening [COMPLETADO]

Se corrigió una regresión de `/editar` donde referencias recientes legítimas fallaban por drift contra YNAB:

- `/editar` usa el `ynab_transaction_id` vivo en YNAB como identidad autoritativa
- Si la transacción existe, payee/monto/categoría cacheados ya no bloquean la edición
- El cache reciente se refresca desde YNAB después de una edición exitosa
- `/deshacer` mantiene validación estricta porque elimina la transacción completa

### E.11 — Executable Harness Gates [COMPLETADO]

Se agregó la primera capa ejecutable de validación del workflow documental antes del deploy:

- `scripts/harness/check_docs.py` entrega diagnósticos locales de SPEC/PLAN/ADR y agent docs
- `scripts/harness/verify.py --ci` bloquea Railway cuando detecta drift documental
- El build de Railway ahora corre el harness antes de `pytest`
- Se archivaron documentos completados que seguían activos y se actualizaron referencias de agentes obsoletas

### E.12 — Financial Advisor Phase 3 Dashboard [COMPLETADO]

Se reemplazó el placeholder autenticado del advisor con el primer dashboard útil de lectura:

- Dashboard web autenticado para `/advisor`
- Métricas por período para mes, semana y día
- Datos leídos desde YNAB y repositorios por usuario
- Mantiene la sesión web emitida desde Telegram

### E.13 — HTTP API and Prepared Expense Hardening [COMPLETADO]

Se endureció la ruta HTTP y el flujo preparado de gastos antes de ampliar superficies web:

- Endpoint HTTP autenticado para registrar gastos
- Validación compartida de requests HTTP
- Autenticación bearer con comparación constante
- Sanitización de errores del callback OAuth
- Contrato tipado para prepared expenses

### E.14 — SQLite Thread-Safe Compatibility Hardening [COMPLETADO]

Se corrigió la gestión de conexiones SQLite mientras seguía existiendo como ruta runtime o compatibilidad:

- Conexiones SQLite por thread en `DatabaseManager`
- Separación entre conexión de inicialización y conexiones runtime
- Pruebas de repositorios preservadas para compatibilidad y migración

### E.15 — YNAB Source-of-Truth Hardening [COMPLETADO]

Se formalizó que YNAB es la fuente financiera autoritativa:

- Totales de gasto desde transacciones
- Salud presupuestal desde snapshots de categorías
- Balances desde campos de cuentas
- `/recent`, `/editar` y `/deshacer` tratados como superficies de conveniencia

### E.16 — Temporary Monthly Summary Disablement [COMPLETADO]

Se deshabilitó temporalmente `/resumen` cuando el flujo mensual necesitó protección:

- Mensaje seguro en español para usuarios
- Callback mensual protegido mientras estaba deshabilitado
- Documentación archivada del estado temporal

### E.17 — Compact Monthly /resumen [COMPLETADO]

Se rediseñó `/resumen mes` para hacerlo compacto y accionable:

- Resumen mensual priorizado por estado de presupuesto
- Botones inline para ver categorías y presupuesto
- Agregación split-aware para vistas de período
- Alineación de métricas mensuales del advisor con actividad y balances de YNAB

### E.18 — Harness Roadmap Coherence [COMPLETADO]

Se amplió el harness documental para que ROADMAP sea el índice actualizado del trabajo completado:

- Salida JSON para diagnósticos locales y CI
- Validación de marcadores ROADMAP en SPECs implementadas y PLANs completados
- Verificación de checkboxes en PLANs completados archivados
- ROADMAP actualizado con features implementadas que estaban solo en SPEC/PLAN archivados

### E.19 — Railway Config Harness [COMPLETADO]

Se amplió el harness para validar que Railway siga ejecutando el gate correcto antes del deploy:

- `railway.toml` debe existir y ser TOML válido
- El build debe ejecutar `python scripts/harness/verify.py --ci` antes de `pytest`
- El start command debe conservar `python main.py` como entrypoint esperado
- La validación usa solo librería estándar y aparece en salidas texto/JSON del harness

### E.20 — Harness Command Registry [COMPLETADO]

Se centralizaron los comandos operativos vivos para evitar drift entre agentes, docs y Railway:

- `scripts/harness/commands.py` define los comandos canónicos del harness, tests, runtime y Railway
- `docs/harness/COMMANDS.md` documenta la fuente de verdad para humanos y agentes
- El harness valida que entrypoints de agentes y workflow docs referencien los comandos esperados
- La validación de Railway reutiliza las mismas constantes del registro

### E.21 — Spec Framework Evaluation [COMPLETADO]

Se evaluaron OpenSpec, OpenSDD, OpenSPDD/SPDD y Superpowers contra el workflow actual:

- Se mantiene el workflow repo-local SPEC/PLAN/ADR como fuente autoritativa
- No se adopta OpenSpec/OpenSDD/OpenSPDD como dependencia o estructura obligatoria por ahora
- Se conserva Superpowers como disciplina opcional del agente, no como proceso canónico del repo
- Se recomienda tomar ideas de SPDD para el próximo harness de invariantes financieras

### E.22 — Runtime Financial Invariant Harness [COMPLETADO]

Se amplió el harness para proteger evidencia ejecutable de las invariantes financieras principales:

- Conversión de gastos a milliunits negativos antes de enviar a YNAB
- Totales de gasto respaldados por transacciones, no por estado local reciente
- Salud presupuestal desde snapshots de categorías y balances desde campos de cuentas
- `/recent`, `/editar` y `/deshacer` tratados como superficies de conveniencia
- Comando local `.venv/bin/python scripts/harness/check_financial_invariants.py` para diagnóstico directo
- `verify.py --ci` bloquea si desaparece la evidencia documental, de código o de tests

### E.23 — Behavioral Invariant Fixtures [COMPLETADO]

Se amplió el harness financiero desde evidencia estática hacia fixtures ejecutables:

- Fixtures determinísticos para agregación split-aware y transacciones shared zero-sum
- Validación ejecutable de gasto neto tipo Reflect y snapshots de categorías con `balance` de YNAB
- Validación ejecutable de reconciliación: `/editar` confía en identidad viva de YNAB y `/deshacer` bloquea referencias stale
- Comando local `.venv/bin/python scripts/harness/check_behavioral_invariants.py` para diagnóstico directo
- `verify.py --ci` bloquea si las invariantes conductuales fallan antes de correr `pytest`

### E.24 — Behavioral Invariant Manifest [COMPLETADO]

Se hizo explícita la propiedad y el alcance de cada fixture conductual del harness:

- `scripts/harness/behavioral_invariants.toml` declara ID, etiqueta, área de riesgo, regla protegida, owner path y assertion
- El harness valida metadata requerida, IDs duplicados, owner paths faltantes y assertions desconocidas
- La salida de invariantes conductuales ahora muestra área de riesgo y regla protegida
- La ejecución sigue usando mapeo explícito de assertions y librería estándar
- `verify.py --ci` bloquea si el manifiesto o alguna fixture conductual queda incoherente

### E.25 — Behavioral Coverage Index [COMPLETADO]

Conectar cada fixture conductual con su evidencia de pytest y documentación/ADR:

- Extender `scripts/harness/behavioral_invariants.toml` con evidencia de tests y docs [COMPLETADO]
- Validar paths y snippets sin ejecutar pytest desde el harness [COMPLETADO]
- Detectar gaps entre regla protegida, fixture ejecutable, test coverage y fuente documental [COMPLETADO]
- Mantener salida concisa y compatible con `verify.py --ci` [COMPLETADO]

### E.26 — Additional Behavioral Fixtures [COMPLETADO]

Ampliar el set de fixtures conductuales de alto riesgo financiero:

- Seleccionar un primer batch pequeño después del coverage index [COMPLETADO]
- Cubrir más flujos financieros sin llamadas externas ni base de datos [COMPLETADO]
- Registrar cada fixture nueva en el manifiesto con owner, regla protegida y evidencia [COMPLETADO]
- Tratar cualquier drift descubierto como bug, no como debilitamiento del harness [COMPLETADO]

### E.27 — Harness Output UX [COMPLETADO]

Mejorar la legibilidad de diagnósticos locales y logs de Railway:

- Hacer más accionables los mensajes de fallo [COMPLETADO]
- Preservar compatibilidad JSON y contratos de exit code [COMPLETADO]
- Mantener salida determinística para tests y CI [COMPLETADO]
- Evitar dependencias externas o dashboards prematuros [COMPLETADO]

### E.28 — Handoff Resume Prompt [COMPLETADO]

Se mejoró el handoff entre agentes para que `docs/wip_state.md` incluya un prompt reutilizable:

- `docs/AI_WORKFLOW.md` exige un campo `Resume Prompt` en el protocolo de handoff
- El harness valida los campos requeridos cuando existe `docs/wip_state.md`
- La ausencia de `docs/wip_state.md` queda como `WARN` porque es estado local ignorado, no un bloqueo de Railway
- Los tests cubren el campo faltante y el caso de checkout limpio sin estado local

### E.29 — Project Instructions Refactoring [COMPLETADO]

Consolidar las instrucciones compartidas de agentes para reducir duplicación y drift:

- `AGENTS.md` es la fuente canónica de instrucciones compartidas del proyecto
- `CLAUDE.md` y `GEMINI.md` quedaron como wrappers delgados con identidad y role mapping específico
- El harness valida que los wrappers referencien `AGENTS.md` y no dupliquen secciones compartidas
- Las instrucciones de comandos apuntan al command registry canónico

### E.30 — Cross-Client Agent Contracts [COMPLETADO]

Se creó una fuente canónica de contratos de agentes reutilizable por Claude, Codex, Gemini CLI y futuros clientes:

- `docs/agents/` define un contrato por rol lógico del workflow
- `AGENTS.md`, `CLAUDE.md` y `GEMINI.md` mapean cada rol a su contrato canónico
- `.claude/agents/` conserva los agentes nativos de Claude como adapters que referencian `docs/agents/`
- El harness falla si falta un contrato canónico, un wrapper no lo referencia o un adapter de Claude pierde su referencia
- Skillshare queda como distribución opcional, no como fuente de verdad del repo
