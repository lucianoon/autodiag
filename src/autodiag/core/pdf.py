from __future__ import annotations

from pathlib import Path


def _playwright_sync_api_available() -> bool:
    try:
        import playwright as _pw  # noqa: F401  # type: ignore[import-not-found]
        from playwright import sync_api as _sa  # noqa: F401  # type: ignore[import-not-found]

        return True
    except Exception:
        return False


def render_html_to_pdf(html: str, output_path: Path) -> Path:
    """Renderiza HTML (string) num arquivo PDF via Playwright Chromium headless.

    O conteúdo é injetado com ``page.set_content()`` — o Chromium nunca faz
    GET a uma URL derivada da requisição, o que elimina SSRF via header Host.

    Requer que a opcional `playwright` esteja instalada
    e o binário do Chromium tenha sido baixado com
    `playwright install chromium`. Levanta RuntimeError caso contrário.

    Parâmetros:
        html: documento HTML completo já renderizado.
        output_path: Path destino do PDF; se o diretório pai não existir
            ele é criado automaticamente.

    Retorna:
        O mesmo `output_path` passado por parâmetro, agora contendo o PDF.
    """
    if not _playwright_sync_api_available():
        raise RuntimeError(
            "Biblioteca `playwright` não está instalada. Rode "
            "`pip install playwright` (ou `uv add playwright`) depois "
            "`playwright install chromium` para habilitar exportação PDF."
        )

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        from playwright.sync_api import sync_playwright
    except Exception as e:  # pragma: no cover - depende runtime
        raise RuntimeError(
            "Módulo playwright está instalado mas falhou ao importar a "
            f"API sync: {e}. Confirme se `playwright install chromium` foi "
            "executado."
        ) from e

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                ctx = browser.new_context(
                    viewport={"width": 794, "height": 1123},
                    locale="pt-BR",
                )
                page = ctx.new_page()
                page.set_content(html, wait_until="load")
                pdf_bytes = page.pdf(
                    format="A4",
                    print_background=True,
                    margin={
                        "top": "10mm",
                        "bottom": "12mm",
                        "left": "12mm",
                        "right": "12mm",
                    },
                )
            finally:
                browser.close()
    except Exception as e:  # pragma: no cover - depende do chromium instalado
        raise RuntimeError(
            "Falha ao renderizar PDF com Playwright. Confira se o Chromium "
            "foi instalado com `playwright install chromium`. Detalhe: "
            f"{type(e).__name__}: {e}"
        ) from e

    output_path.write_bytes(pdf_bytes)
    return output_path
