from domain.exceptions import AdvisorAuthenticationException
from presentation.http.advisor_auth import (
    ADVISOR_SESSION_COOKIE,
    build_clear_session_cookie,
    build_session_cookie,
    get_cookie_value,
)

_ADVISOR_APP_HTML = """<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Advisor YNAB</title>
  <style>
    :root { color-scheme: light; --bg: #f4efe6; --panel: #fffaf2; --ink: #172b1f; --muted: #5e6d63; --accent: #0f7b5f; --accent-soft: #d9efe6; --line: #d9cfbf; --danger: #9f3a2f; }
    * { box-sizing: border-box; }
    body { margin: 0; font-family: Georgia, "Times New Roman", serif; background: radial-gradient(circle at top, #fff8ed, var(--bg)); color: var(--ink); }
    main { max-width: 1080px; margin: 0 auto; padding: 40px 20px 72px; }
    .hero { display: flex; justify-content: space-between; gap: 16px; align-items: flex-start; margin-bottom: 24px; }
    .hero h1 { margin: 0 0 8px; font-size: clamp(2rem, 5vw, 3.2rem); }
    .hero p { margin: 0; max-width: 560px; color: var(--muted); line-height: 1.5; }
    .hero-actions { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }
    .pill { display: inline-block; padding: 7px 12px; border-radius: 999px; background: #e5f3ee; color: var(--accent); font-size: 0.9rem; }
    .shell { display: grid; gap: 18px; }
    .card { background: color-mix(in srgb, var(--panel) 92%, white); border: 1px solid var(--line); border-radius: 22px; padding: 22px; box-shadow: 0 14px 40px rgba(31, 34, 26, 0.06); }
    .toolbar { display: flex; justify-content: space-between; gap: 16px; align-items: center; flex-wrap: wrap; }
    .toolbar h2 { margin: 0; font-size: 1.2rem; }
    .toolbar p { margin: 6px 0 0; color: var(--muted); }
    .periods { display: inline-flex; gap: 8px; padding: 6px; border-radius: 999px; background: #efe5d7; }
    .period-btn { border: 0; background: transparent; color: var(--muted); border-radius: 999px; padding: 10px 14px; cursor: pointer; font: inherit; }
    .period-btn.active { background: var(--accent); color: #fff; }
    .metrics { display: grid; gap: 14px; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); }
    .metric-label { margin: 0 0 10px; color: var(--muted); font-size: 0.85rem; text-transform: uppercase; letter-spacing: 0.08em; }
    .metric-value { margin: 0; font-size: 1.8rem; }
    .metric-note { margin: 8px 0 0; color: var(--muted); }
    .content-grid { display: grid; gap: 18px; grid-template-columns: minmax(0, 1.4fr) minmax(0, 1fr); }
    .trend-bars { display: grid; grid-template-columns: repeat(auto-fit, minmax(14px, 1fr)); gap: 10px; align-items: end; min-height: 220px; margin-top: 18px; }
    .trend-bar-wrap { display: grid; justify-items: center; gap: 8px; }
    .trend-bar { width: 100%; max-width: 20px; min-height: 4px; border-radius: 999px; background: linear-gradient(180deg, #6bb89f 0%, var(--accent) 100%); }
    .trend-label { font-size: 0.78rem; color: var(--muted); }
    .category-list, .budget-list { display: grid; gap: 12px; margin-top: 18px; }
    .row { display: grid; gap: 8px; }
    .row-top { display: flex; justify-content: space-between; gap: 12px; }
    .row-top strong { font-size: 1rem; }
    .row-top span { color: var(--muted); }
    .bar-track { height: 10px; border-radius: 999px; background: #eadfcf; overflow: hidden; }
    .bar-fill { height: 100%; border-radius: 999px; background: linear-gradient(90deg, #0f7b5f, #54a88f); }
    .budget-meta { display: flex; justify-content: space-between; gap: 12px; color: var(--muted); font-size: 0.9rem; }
    .budget-meta .overspent { color: var(--danger); }
    .empty { padding: 28px; border-radius: 18px; background: #fff4ea; border: 1px solid #ebd5c1; }
    .empty h3 { margin: 0 0 10px; }
    .empty p { margin: 0; color: var(--muted); line-height: 1.5; }
    button#logout { background: var(--accent); color: white; border: 0; border-radius: 999px; padding: 10px 16px; cursor: pointer; font: inherit; }
    @media (max-width: 820px) {
      .hero { display: grid; }
      .content-grid { grid-template-columns: 1fr; }
    }
  </style>
</head>
<body>
  <main>
    <div class="hero">
      <div>
        <h1>Advisor financiero</h1>
        <p>Una vista mas amplia de tus gastos para detectar ritmo, categorias dominantes y senales del mes sin salir del flujo actual del bot.</p>
      </div>
      <div class="hero-actions">
        <div id="state" class="pill">Cargando...</div>
        <button id="logout">Cerrar sesion</button>
      </div>
    </div>
    <div class="shell">
      <section class="card">
        <div class="toolbar">
          <div>
            <h2 id="welcome">Cargando dashboard...</h2>
            <p id="period-label"></p>
          </div>
          <div class="periods" aria-label="Selector de periodo">
            <button class="period-btn active" data-period="mes">Mes</button>
            <button class="period-btn" data-period="semana">Semana</button>
            <button class="period-btn" data-period="dia">Dia</button>
          </div>
        </div>
        <div id="empty-state" class="empty" hidden></div>
        <div id="dashboard" hidden>
          <div class="metrics" id="metrics"></div>
          <div class="content-grid" style="margin-top:18px">
            <section class="card">
              <div class="toolbar">
                <div>
                  <h2>Tendencia</h2>
                  <p id="trend-caption">Gasto acumulado por dia dentro del periodo.</p>
                </div>
              </div>
              <div class="trend-bars" id="trend-bars"></div>
            </section>
            <section class="card">
              <div class="toolbar">
                <div>
                  <h2>Categorias destacadas</h2>
                  <p>Las categorias con mayor peso en el periodo seleccionado.</p>
                </div>
              </div>
              <div class="category-list" id="category-list"></div>
            </section>
          </div>
          <section class="card" id="budget-card" style="margin-top:18px" hidden>
            <div class="toolbar">
              <div>
                <h2>Estado del presupuesto</h2>
                <p>Contexto mensual para revisar donde vas por arriba o dentro de lo planeado.</p>
              </div>
            </div>
            <div class="budget-list" id="budget-list"></div>
          </section>
        </div>
      </section>
    </div>
  </main>
  <script>
    const stateEl = document.getElementById('state');
    const welcomeEl = document.getElementById('welcome');
    const periodLabelEl = document.getElementById('period-label');
    const metricsEl = document.getElementById('metrics');
    const trendBarsEl = document.getElementById('trend-bars');
    const categoryListEl = document.getElementById('category-list');
    const budgetCardEl = document.getElementById('budget-card');
    const budgetListEl = document.getElementById('budget-list');
    const dashboardEl = document.getElementById('dashboard');
    const emptyStateEl = document.getElementById('empty-state');
    let bootstrapPayload = null;
    let currentPeriod = 'mes';

    function formatMoney(milliunits) {
      const amount = Math.round((milliunits || 0) / 1000);
      return new Intl.NumberFormat('es-CO', {
        style: 'currency',
        currency: 'COP',
        maximumFractionDigits: 0
      }).format(amount);
    }

    function escapeHtml(value) {
      return String(value || '')
        .replaceAll('&', '&amp;')
        .replaceAll('<', '&lt;')
        .replaceAll('>', '&gt;')
        .replaceAll('"', '&quot;')
        .replaceAll("'", '&#39;');
    }

    function setActivePeriod(period) {
      currentPeriod = period;
      document.querySelectorAll('.period-btn').forEach((button) => {
        button.classList.toggle('active', button.dataset.period === period);
      });
    }

    function renderMetrics(summary) {
      const cards = [
        ['Total gastado', formatMoney(summary.total_spent), summary.period_label],
        ['Transacciones', String(summary.transaction_count), 'Gastos detectados en el periodo'],
        ['Promedio diario', formatMoney(summary.average_daily_spent), `${summary.active_days} dias considerados`],
        ['Categoria principal', summary.top_category_name || 'Sin datos', summary.top_category_amount ? formatMoney(summary.top_category_amount) : 'Todavia sin movimientos']
      ];
      metricsEl.innerHTML = cards.map(([label, value, note]) => `
        <article class="card">
          <p class="metric-label">${escapeHtml(label)}</p>
          <p class="metric-value">${escapeHtml(value)}</p>
          <p class="metric-note">${escapeHtml(note)}</p>
        </article>
      `).join('');
    }

    function renderTrend(points) {
      const max = Math.max(...points.map((point) => point.amount), 0);
      trendBarsEl.innerHTML = points.map((point) => {
        const height = max > 0 ? Math.max(6, Math.round((point.amount / max) * 180)) : 6;
        return `
          <div class="trend-bar-wrap" title="${escapeHtml(point.label)}: ${escapeHtml(formatMoney(point.amount))}">
            <div class="trend-bar" style="height:${height}px"></div>
            <div class="trend-label">${escapeHtml(point.label)}</div>
          </div>
        `;
      }).join('');
    }

    function renderCategories(categories) {
      const max = Math.max(...categories.map((item) => item.amount), 0);
      categoryListEl.innerHTML = categories.map((item) => {
        const width = max > 0 ? Math.max(8, Math.round((item.amount / max) * 100)) : 8;
        return `
          <div class="row">
            <div class="row-top">
              <strong>${escapeHtml(item.category_name)}</strong>
              <span>${escapeHtml(formatMoney(item.amount))}</span>
            </div>
            <div class="bar-track"><div class="bar-fill" style="width:${width}%"></div></div>
          </div>
        `;
      }).join('');
    }

    function renderBudgetStatus(items) {
      if (!items || !items.length) {
        budgetCardEl.hidden = true;
        budgetListEl.innerHTML = '';
        return;
      }
      budgetCardEl.hidden = false;
      budgetListEl.innerHTML = items.map((item) => `
        <div class="row">
          <div class="row-top">
            <strong>${escapeHtml(item.category_name)}</strong>
            <span>${escapeHtml(formatMoney(item.spent))}</span>
          </div>
          <div class="budget-meta">
            <span>Presupuestado: ${escapeHtml(formatMoney(item.budgeted))}</span>
            <span class="${item.status === 'overspent' ? 'overspent' : ''}">
              ${item.status === 'overspent' ? 'Sobregasto' : 'Disponible'}: ${escapeHtml(formatMoney(Math.abs(item.remaining)))}
            </span>
          </div>
        </div>
      `).join('');
    }

    function renderEmptyState(emptyState) {
      if (!emptyState) {
        emptyStateEl.hidden = true;
        emptyStateEl.innerHTML = '';
        dashboardEl.hidden = false;
        return;
      }
      dashboardEl.hidden = true;
      budgetCardEl.hidden = true;
      emptyStateEl.hidden = false;
      emptyStateEl.innerHTML = `
        <h3>${escapeHtml(emptyState.title)}</h3>
        <p>${escapeHtml(emptyState.message)}</p>
      `;
    }

    async function loadBootstrap() {
      const response = await fetch('/api/v1/advisor/bootstrap', { credentials: 'include' });
      if (!response.ok) {
        window.location.href = '/';
        return null;
      }
      bootstrapPayload = await response.json();
      stateEl.textContent = 'Estado: ' + bootstrapPayload.advisor_state;
      welcomeEl.textContent = `Hola, ${bootstrapPayload.user.display_name}`;
      return bootstrapPayload;
    }

    async function loadDashboard(period) {
      setActivePeriod(period);
      const response = await fetch(`/api/v1/advisor/dashboard?period=${encodeURIComponent(period)}`, { credentials: 'include' });
      if (response.status === 401) {
        window.location.href = '/';
        return;
      }
      const payload = await response.json();
      stateEl.textContent = 'Estado: ' + payload.advisor_state;
      periodLabelEl.textContent = payload.summary.period_label || 'Selecciona un periodo para ver el detalle.';
      renderEmptyState(payload.empty_state);
      if (payload.empty_state && payload.empty_state.code !== 'no_transactions') {
        return;
      }
      dashboardEl.hidden = false;
      renderMetrics(payload.summary);
      renderTrend(payload.trend || []);
      renderCategories(payload.top_categories || []);
      renderBudgetStatus(payload.budget_status);
    }

    document.getElementById('logout').addEventListener('click', async () => {
      await fetch('/api/v1/advisor/logout', { method: 'POST', credentials: 'include' });
      window.location.href = '/';
    });
    document.querySelectorAll('.period-btn').forEach((button) => {
      button.addEventListener('click', () => loadDashboard(button.dataset.period));
    });
    loadBootstrap().then((payload) => {
      if (!payload) return;
      loadDashboard(currentPeriod);
    });
  </script>
</body>
</html>"""

_AUTH_ERROR_HTML = """<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Advisor YNAB</title></head>
<body style="font-family:sans-serif;text-align:center;padding:60px">
<h1>No se pudo abrir el advisor</h1>
<p>{message}</p>
<p>Vuelve a intentarlo desde <strong>/analisis</strong> en Telegram.</p>
</body></html>"""


class AdvisorPageHandler:
    def __init__(self, container):
        self._advisor_access_service = container.get_advisor_access_service()
        self._config = container.get_config()

    def handle_launch(self, token: str | None) -> tuple[int, str, str | bytes, dict]:
        try:
            session_token = self._advisor_access_service.exchange_launch_token(token or "")
        except AdvisorAuthenticationException as exc:
            return 401, "html", _AUTH_ERROR_HTML.format(message=exc.user_message), {
                "Set-Cookie": build_clear_session_cookie(self._is_secure())
            }

        return 302, "bytes", b"", {
            "Location": "/advisor",
            "Set-Cookie": build_session_cookie(session_token, self._is_secure()),
        }

    def handle_page(self, headers: dict) -> tuple[int, str, str | bytes, dict]:
        session_token = get_cookie_value(headers, ADVISOR_SESSION_COOKIE)
        telegram_id = self._advisor_access_service.get_session_telegram_id(session_token)
        if telegram_id is None:
            return 401, "html", _AUTH_ERROR_HTML.format(
                message="Tu sesion del advisor no es valida o ya expiro."
            ), {"Set-Cookie": build_clear_session_cookie(self._is_secure())}
        return 200, "html", _ADVISOR_APP_HTML, {}

    def _is_secure(self) -> bool:
        return self._config.resolved_advisor_base_url.startswith("https://")
