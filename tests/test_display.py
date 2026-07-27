"""A camada de display não deve interpretar texto não confiável como marcação.

Mensagens de exceção e saída de modelo chegam aqui como texto arbitrário. O rich
trata ``[algo]`` como tag de estilo, então sem escape a instrução
``pip install 'autodiag[openai]'`` sai como ``pip install 'autodiag'`` e um
``[/PCV]`` na análise derruba o painel com ``MarkupError``.
"""

import pytest
from rich.console import Console

from autodiag.ui import display


@pytest.fixture
def captured(monkeypatch):
    """Console que grava em buffer, com largura fixa para o texto não quebrar."""
    console = Console(record=True, width=200, legacy_windows=False)
    monkeypatch.setattr(display, "console", console)
    return console


class TestMensagensPreservamColchetes:
    def test_warn_mantem_o_extra_do_pip(self, captured):
        display.warn("Instale com: pip install 'autodiag[openai]'")
        assert "autodiag[openai]" in captured.export_text()

    def test_err_mantem_colchetes(self, captured):
        display.err("Falhou em [etapa 3]")
        assert "[etapa 3]" in captured.export_text()

    def test_ok_mantem_colchetes(self, captured):
        display.ok("Concluído [2 de 2]")
        assert "[2 de 2]" in captured.export_text()

    def test_texto_que_parece_tag_de_fechamento_nao_quebra(self, captured):
        display.warn("Erro da API: tag [/bold] inesperada")
        assert "[/bold]" in captured.export_text()


class TestAnalysisPanel:
    def test_preserva_marcadores_entre_colchetes(self, captured):
        display.analysis_panel("Urgência: [CRÍTICO]\nCausa: sensor MAF [ver P0101]")
        out = captured.export_text()
        assert "[CRÍTICO]" in out
        assert "[ver P0101]" in out

    def test_nao_quebra_com_tag_de_fechamento_orfa(self, captured):
        """Antes: MarkupError depois de a chamada ao modelo já ter sido paga."""
        display.analysis_panel("Custo: R$ [200-400], trocar válvula [/PCV]")
        assert "[/PCV]" in captured.export_text()

    def test_urgencia_desconhecida_nao_quebra(self, captured):
        display.analysis_panel("texto", urgency="valor-inesperado")
        assert "texto" in captured.export_text()
