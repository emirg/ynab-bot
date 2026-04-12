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
    :root { color-scheme: light; --bg: #f4efe6; --panel: #fffaf2; --ink: #172b1f; --muted: #5e6d63; --accent: #0f7b5f; --line: #d9cfbf; }
    body { margin: 0; font-family: Georgia, "Times New Roman", serif; background: radial-gradient(circle at top, #fff8ed, var(--bg)); color: var(--ink); }
    main { max-width: 720px; margin: 0 auto; padding: 48px 20px 72px; }
    section { background: color-mix(in srgb, var(--panel) 92%, white); border: 1px solid var(--line); border-radius: 20px; padding: 24px; box-shadow: 0 14px 40px rgba(31, 34, 26, 0.06); }
    h1 { margin: 0 0 8px; font-size: 2rem; }
    p { color: var(--muted); line-height: 1.5; }
    .pill { display: inline-block; margin-top: 12px; padding: 6px 10px; border-radius: 999px; background: #e5f3ee; color: var(--accent); font-size: 0.9rem; }
    dl { margin: 24px 0 0; display: grid; grid-template-columns: 1fr; gap: 12px; }
    dt { font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.08em; color: var(--muted); }
    dd { margin: 4px 0 0; font-size: 1rem; }
    button { margin-top: 20px; background: var(--accent); color: white; border: 0; border-radius: 999px; padding: 10px 16px; cursor: pointer; }
  </style>
</head>
<body>
  <main>
    <section>
      <h1>Advisor financiero</h1>
      <p>Esta es la primera entrada autenticada al advisor. El dashboard y el analisis vienen en la siguiente fase.</p>
      <div id="state" class="pill">Cargando...</div>
      <dl id="details"></dl>
      <button id="logout">Cerrar sesion</button>
    </section>
  </main>
  <script>
    async function loadBootstrap() {
      const response = await fetch('/api/v1/advisor/bootstrap', { credentials: 'include' });
      if (!response.ok) {
        window.location.href = '/';
        return;
      }
      const payload = await response.json();
      document.getElementById('state').textContent = 'Estado: ' + payload.advisor_state;
      const details = document.getElementById('details');
      const rows = [
        ['Usuario', payload.user.display_name],
        ['YNAB', payload.ynab_connected ? 'Conectado' : 'Pendiente'],
        ['Presupuesto', payload.budget_name || payload.budget_id || 'Pendiente'],
        ['Cuenta por defecto', payload.default_account_name || 'Pendiente'],
        ['Onboarding', payload.onboarding_state]
      ];
      details.innerHTML = rows.map(([label, value]) => `<div><dt>${label}</dt><dd>${value}</dd></div>`).join('');
    }
    document.getElementById('logout').addEventListener('click', async () => {
      await fetch('/api/v1/advisor/logout', { method: 'POST', credentials: 'include' });
      window.location.href = '/';
    });
    loadBootstrap();
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
