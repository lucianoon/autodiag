from __future__ import annotations

import base64
import html
import io
import socket
from dataclasses import dataclass

from autodiag.core.config import Branding, get_branding
from autodiag.core.cost_estimates import estimate_session_costs, format_brl
from autodiag.core.dtc import lookup
from autodiag.core.inspection import build_inspection_verdict

try:
    import qrcode  # type: ignore[import-untyped]
    from qrcode.image.pil import PilImage  # type: ignore[import-untyped]

    _QRCODE_AVAILABLE = True
except Exception:  # pragma: no cover - dependência opcional só para runtime
    _QRCODE_AVAILABLE = False
    qrcode = None
    PilImage = None


@dataclass(frozen=True)
class Report:
    session: dict
    previous: dict | None
    vehicle_history: list[dict]
    dtcs: list[dict]
    diff: dict
    branding: Branding | None = None
    download_url: str | None = None


def _local_ip_candidates() -> list[str]:
    """Retorna IPs locais candidatos para montar URL de download via QR."""
    candidates: list[str] = []
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            if ip:
                candidates.append(ip)
        finally:
            s.close()
    except Exception:
        pass
    try:
        hostname = socket.gethostname()
        for info in socket.getaddrinfo(hostname, None, socket.AF_INET):
            raw = info[4][0]
            if not isinstance(raw, str):
                continue
            ip_str = raw
            if ip_str and ip_str not in candidates and not ip_str.startswith("127."):
                candidates.append(ip_str)
    except Exception:
        pass
    for extra in ("127.0.0.1", "localhost"):
        if extra not in candidates:
            candidates.append(extra)
    return candidates


def _qrcode_data_uri(url: str) -> str | None:
    if not _QRCODE_AVAILABLE or not url or qrcode is None:
        return None
    try:
        img = qrcode.make(url, image_factory=PilImage, box_size=4, border=2)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        b64 = base64.b64encode(buf.getvalue()).decode("ascii")
        return f"data:image/png;base64,{b64}"
    except Exception:
        return None


def build_report(
    session: dict,
    previous: dict | None = None,
    vehicle_history: list[dict] | None = None,
    branding: Branding | None = None,
    download_url: str | None = None,
) -> Report:
    if branding is None:
        branding = get_branding()
    dtc_codes = session.get("dtc_codes") or []
    dtcs: list[dict] = []
    for code in dtc_codes:
        info = lookup(code)
        dtcs.append(
            {
                "code": code,
                "description": info.description if info else "—",
                "severity": info.severity if info else "informativo",
                "system": info.system if info else "—",
                "causes": info.causes if info else [],
            }
        )

    prev_codes = set(previous.get("dtc_codes") or []) if previous else set()
    cur_codes = set(dtc_codes)
    added = sorted(cur_codes - prev_codes)
    removed = sorted(prev_codes - cur_codes)

    fields = [
        ("rpm", "RPM", "rpm"),
        ("speed", "Velocidade", "km/h"),
        ("coolant_temp", "Temperatura do motor", "°C"),
        ("maf", "MAF", "g/s"),
        ("fuel_trim_short", "Fuel trim curto B1", "%"),
        ("fuel_trim_long", "Fuel trim longo B1", "%"),
        ("o2", "O2 B1S1", "V"),
        ("km", "Quilometragem", "km"),
    ]
    thresholds = {
        "rpm": 200,
        "speed": 10,
        "coolant_temp": 5,
        "maf": 0.5,
        "fuel_trim_short": 3.0,
        "fuel_trim_long": 3.0,
        "o2": 0.05,
        "km": 500,
    }
    numeric_changes: list[dict] = []
    if previous:
        for key, label, unit in fields:
            cur = session.get(key)
            prev = previous.get(key)
            if cur is None or prev is None:
                continue
            if not (isinstance(cur, (int, float)) and isinstance(prev, (int, float))):
                continue
            if cur == prev:
                continue

            delta = cur - prev
            threshold = thresholds.get(key)
            if threshold is not None and abs(delta) < threshold:
                continue

            pct = None
            if prev not in (0, 0.0):
                pct = delta / prev

            numeric_changes.append(
                {
                    "key": key,
                    "label": label,
                    "unit": unit,
                    "from": prev,
                    "to": cur,
                    "delta": delta,
                    "pct": pct,
                    "severity": "atencao",
                }
            )

    diff = {"dtc_added": added, "dtc_removed": removed, "numeric_changes": numeric_changes}
    return Report(
        session=session,
        previous=previous,
        vehicle_history=vehicle_history or [],
        dtcs=dtcs,
        diff=diff,
        branding=branding,
        download_url=download_url,
    )


def render_report_html(report: Report) -> str:
    s = report.session
    triage = s.get("triage") or {}
    sid = s.get("id") or ""
    vhist = report.vehicle_history

    def esc(x) -> str:
        return html.escape(str(x if x is not None else "—"))

    def qr_block() -> str:
        raw_url = report.download_url
        if not raw_url:
            candidates = _local_ip_candidates()
            ip = candidates[0] if candidates else "127.0.0.1"
            raw_url = f"http://{ip}:8000/report/{sid}/download"
        data_uri = _qrcode_data_uri(raw_url)
        if not data_uri:
            return ""
        return (
            '<div class="card mt-3 p-3 d-flex flex-row '
            "justify-content-between align-items-center flex-wrap gap-2\" "
            'style="background:#010409;border:1px solid #30363d;">'
            '<div class="small text-muted"><span class="me-2">📱 '
            '<strong class="text-white">Baixe no celular</strong></span>'
            "· escaneie o QR ou acesse "
            f'<a href="{esc(raw_url)}" target="_blank" rel="noopener" '
            f'class="text-decoration-underline">{esc(raw_url)}</a>'
            "</div>"
            f'<img src="{esc(data_uri)}" alt="QR de download" '
            'style="width:96px;height:96px;image-rendering:pixelated;'
            'background:#fff;border-radius:4px;">'
            "</div>"
        )

    sev = {"critico": "danger", "atencao": "warning", "informativo": "info"}
    sev_cls = sev.get(s.get("urgency") or "informativo", "secondary")

    def badge(label: str, kind: str) -> str:
        return f'<span class="badge text-bg-{kind}">{esc(label)}</span>'

    def list_items(items: list[str]) -> str:
        if not items:
            return "<div class='text-muted'>—</div>"
        return "<ul class='mb-0'>" + "".join(f"<li>{esc(i)}</li>" for i in items) + "</ul>"

    def dtc_table(dtcs: list[dict]) -> str:
        if not dtcs:
            return "<div class='text-muted'>Nenhum DTC encontrado.</div>"
        rows = []
        for d in dtcs:
            d_sev = sev.get(d["severity"], "secondary")
            rows.append(
                "<tr>"
                f"<td><code>{esc(d['code'])}</code></td>"
                f"<td class='small'>{esc(d['description'])}</td>"
                f"<td>{badge(d['severity'], d_sev)}</td>"
                f"<td class='small text-muted'>{esc(d['system'])}</td>"
                "</tr>"
            )
        return (
            "<div class='table-responsive'>"
            "<table class='table table-sm table-dark align-middle mb-0'>"
            "<thead><tr><th>Código</th><th>Descrição</th><th>Urgência</th><th>Sistema</th></tr></thead>"
            "<tbody>"
            + "".join(rows)
            + "</tbody></table></div>"
        )

    def kpi(label: str, value: str) -> str:
        return (
            "<div class='col-md-3 col-sm-6 mb-3'>"
            "<div class='card h-100'><div class='card-body py-3'>"
            f"<div class='text-muted small mb-1'>{esc(label)}</div>"
            f"<div class='fw-bold'>{value}</div>"
            "</div></div></div>"
        )

    def triage_block() -> str:
        if not triage:
            return "<div class='text-muted'>Sem triagem.</div>"
        drive = triage.get("drive_advice") or "—"
        drive_meta = {
            "pare": ("PARE", "danger"),
            "cautela": ("RODE COM CAUTELA", "warning"),
            "pode_rodar": ("PODE RODAR", "success"),
        }
        drive_label, drive_kind = drive_meta.get(drive, (str(drive).upper(), sev_cls))
        obs = triage.get("observations") or []
        obs_rows = []
        for o in obs:
            o_kind = sev.get(o.get("severity") or "informativo", "secondary")
            obs_rows.append(
                "<div class='d-flex justify-content-between border-bottom "
                "border-secondary py-1 small'>"
                f"<span class='text-muted'>{esc(o.get('label'))}</span>"
                f"<span>{esc(o.get('value'))} {badge(o.get('severity') or '', o_kind)}</span>"
                "</div>"
            )
        obs_html = "".join(obs_rows) if obs_rows else "<div class='text-muted'>—</div>"
        return (
            f"<div class='mb-2'><strong>{esc(triage.get('headline') or '')}</strong></div>"
            "<div class='d-flex align-items-center gap-2 mb-3'>"
            "<span class='text-muted small'>Orientação:</span>"
            f"{badge(drive_label, drive_kind)}"
            "</div>"
            f"<div class='mb-3'>{obs_html}</div>"
            "<div class='row g-3'>"
            "<div class='col-md-4'><div class='text-muted small mb-1'>Causas prováveis</div>"
            f"{list_items(triage.get('likely_causes') or [])}</div>"
            "<div class='col-md-4'><div class='text-muted small mb-1'>"
            "Testes sugeridos (ordem)</div>"
            f"{list_items(triage.get('recommended_tests') or [])}</div>"
            "<div class='col-md-4'><div class='text-muted small mb-1'>O que não fazer</div>"
            f"{list_items(triage.get('dont_do') or [])}</div>"
            "</div>"
        )

    diff = report.diff
    delta_dtcs = ""
    if report.previous:
        added = diff.get("dtc_added") or []
        removed = diff.get("dtc_removed") or []
        changes = diff.get("numeric_changes") or []
        lines = []
        if added:
            lines.append(
                "<div class='mb-1'><span class='text-muted small'>DTCs novos:</span> "
                + " ".join(f"<code>{esc(c)}</code>" for c in added)
                + "</div>"
            )
        if removed:
            lines.append(
                "<div class='mb-1'><span class='text-muted small'>DTCs resolvidos:</span> "
                + " ".join(f"<code>{esc(c)}</code>" for c in removed)
                + "</div>"
            )
        if changes:
            def fmt_num(x) -> str:
                if isinstance(x, int):
                    return str(x)
                if isinstance(x, float) and x.is_integer():
                    return str(int(x))
                if isinstance(x, float):
                    return f"{x:.2f}"
                return str(x)

            rows = []
            for ch in changes:
                ch_sev = ch.get("severity") or "informativo"
                ch_kind = sev.get(ch_sev, "secondary")
                delta = ch.get("delta")
                pct = ch.get("pct")
                delta_str = "—"
                if isinstance(delta, (int, float)):
                    delta_str = f"{fmt_num(delta)} {esc(ch['unit'])}"
                    if delta > 0:
                        delta_str = f"+{delta_str}"
                pct_str = "—"
                if isinstance(pct, (int, float)):
                    pct_str = f"{pct * 100:+.0f}%"

                rows.append(
                    "<tr>"
                    f"<td class='small text-muted'>{esc(ch['label'])}</td>"
                    f"<td class='small'>{esc(ch['from'])} {esc(ch['unit'])}</td>"
                    f"<td class='small'>{esc(ch['to'])} {esc(ch['unit'])}</td>"
                    f"<td class='small'>{esc(delta_str)}</td>"
                    f"<td class='small'>{esc(pct_str)}</td>"
                    f"<td>{badge(ch_sev, ch_kind)}</td>"
                    "</tr>"
                )
            lines.append(
                "<div class='table-responsive mt-2'>"
                "<table class='table table-sm table-dark mb-0'>"
                "<thead><tr><th>Parâmetro</th><th>Antes</th><th>Agora</th><th>Δ</th><th>%</th><th>Nível</th></tr></thead>"
                "<tbody>" + "".join(rows) + "</tbody></table></div>"
            )
        delta_dtcs = "".join(lines) or "<div class='text-muted'>Sem comparação disponível.</div>"

    analysis = s.get("diagnosis") or ""
    notes = s.get("notes") or ""
    tags: list[str] = s.get("tags") or []
    branding = report.branding or get_branding()

    def branding_block() -> str:
        name = getattr(branding, "workshop_name", "") or ""
        if not any(getattr(branding, f, "") for f in Branding.__dataclass_fields__):
            return ""
        pieces = []
        if getattr(branding, "logo_url", ""):
            pieces.append(
                f'<img src="{esc(branding.logo_url)}" alt="logo" '
                'style="max-height:48px;max-width:160px;margin-right:16px;">'
            )
        name_line = []
        if name:
            name_line.append(f'<h5 class="mb-0">{esc(name)}</h5>')
        subline = []
        for key, lbl in [
            ("mechanic_name", "Mecânico"),
            ("phone", "Tel"),
            ("email", "E-mail"),
            ("address", "End."),
        ]:
            v = getattr(branding, key, "") or ""
            if v:
                subline.append(f"{esc(lbl)}: {esc(v)}")
        name_html = ("<div>" + "".join(name_line)) if name_line else "<div>"
        if subline:
            name_html += f'<div class="small text-muted mt-1">{" · ".join(subline)}</div>'
        name_html += "</div>"
        pieces.append(name_html)
        if not pieces:
            return ""
        return (
            "<div class='d-flex align-items-center mb-3 p-3 rounded' "
            "style='background:#010409;border:1px solid #30363d;'>"
            + "".join(pieces)
            + "</div>"
        )

    def notes_block() -> str:
        header = getattr(branding, "notes_header", "") or "Observações / Próximos passos"
        if not notes and not tags:
            return ""
        tags_html = ""
        if tags:
            tags_html = (
                '<div class="mb-2 d-flex flex-wrap gap-2">'
                + "".join(
                    f'<span class="badge text-bg-info">{esc(t)}</span>'
                    for t in tags
                )
                + "</div>"
            )
        notes_html = esc(notes) if notes else "<span class='text-muted'>—</span>"
        return (
            "<div class='col-12'>"
            "<div class='card'>"
            f"<div class='card-header small text-muted py-2'>{esc(header)}</div>"
            f"<div class='card-body'>{tags_html}<div>{notes_html}</div></div>"
            "</div></div>"
        )

    def cost_block() -> str:
        saved_min = int(s.get("cost_min") or 0)
        saved_max = int(s.get("cost_max") or 0)
        dtcs_list: list[str] = [str(c) for c in (s.get("dtc_codes") or []) if c]
        if saved_min <= 0 and saved_max <= 0 and dtcs_list:
            total_min, total_max, items = estimate_session_costs(dtcs_list)
        else:
            total_min, total_max = saved_min, saved_max
            items = []
            for code in dtcs_list:
                info = lookup(code)
                _, _ = estimate_session_costs([code])[:2]
                per_min, per_max, _ = estimate_session_costs([code])
                desc = info.description if info else ""
                sev = info.severity if info else "informativo"
                items.append(
                    {
                        "code": code,
                        "description": desc,
                        "min_cents": per_min,
                        "max_cents": per_max,
                        "severity": sev,
                    }
                )
        if total_min <= 0 and total_max <= 0 and not dtcs_list:
            return (
                "<div class='col-12'><div class='card'><div class='card-header "
                "small text-muted py-2'>🛠️  Orçamento estimado</div>"
                "<div class='card-body'><p class='mb-0 text-success'><strong>"
                "Não há falhas identificadas</strong> — custo de reparo "
                "estimado R$ 0,00.</p></div></div></div>"
            )
        detail_rows: list[str] = []
        sev_cls_cost = {
            "critico": "danger",
            "atencao": "warning",
            "informativo": "success",
        }
        for it in items:
            code = str(it.get("code") or "—")
            desc = str(it.get("description") or "—")
            sev = str(it.get("severity") or "informativo")
            badge_cls = sev_cls_cost.get(sev, "secondary")
            mn = int(it.get("min_cents") or 0)
            mx = int(it.get("max_cents") or 0)
            faixa = (
                f"{format_brl(mn)} a {format_brl(mx)}"
                if mn and mx
                else format_brl(max(mn, mx))
            )
            detail_rows.append(
                "<tr>"
                f"<td><code>{esc(code)}</code></td>"
                f"<td>{esc(desc)}</td>"
                f"<td><span class='badge bg-{badge_cls}'>{esc(sev)}</span></td>"
                f"<td class='text-end'>{esc(faixa)}</td>"
                "</tr>"
            )
        table_html = ""
        if detail_rows:
            table_html = (
                "<table class='table table-sm table-hover mb-0 mt-3'>"
                "<thead><tr><th>Código</th><th>Descrição</th>"
                "<th>Severidade</th><th class='text-end'>Faixa estimada</th></tr></thead>"
                f"<tbody>{''.join(detail_rows)}</tbody></table>"
            )
        faixa_total = (
            f"{format_brl(total_min)} a {format_brl(total_max)}"
            if total_min and total_max
            else format_brl(max(total_min, total_max))
        )
        return (
            "<div class='col-12'><div class='card'>"
            "<div class='card-header small text-muted py-2'>🛠️  Orçamento estimado</div>"
            "<div class='card-body'>"
            f"<div class='mb-2 fs-5'>Faixa total: <strong style='color:#58a6ff;'>"
            f"{esc(faixa_total)}</strong></div>"
            f"{table_html}"
            "<p class='mb-0 mt-2 small text-muted'>*Valores estimados para região "
            "Sudeste do Brasil. Podem variar conforme modelo/ano do veículo, peça "
            "original ou paralela, complexidade de instalação e política de preços "
            "da oficina. Não inclui mão de obra de diagnóstico prévio.</p>"
            "</div></div></div>"
        )

    def freeze_frame_block() -> str:
        ff = s.get("freeze_frame") or {}
        if not isinstance(ff, dict) or not any(k != "raw" for k in ff):
            return ""
        pairs = [
            ("dtc_code",        "DTC do frame",         ""),
            ("rpm",             "RPM",                  "rpm"),
            ("speed_kmh",       "Velocidade",           "km/h"),
            ("coolant_temp_c",  "Temp. motor",         "°C"),
            ("engine_load_pct", "Carga do motor",      "%"),
            ("throttle_pct",    "Travão (throttle)",    "%"),
            ("maf_g_s",         "MAF",                  "g/s"),
            ("fuel_trim_short_b1","FT curto B1",       "%"),
            ("fuel_trim_long_b1","FT longo B1",        "%"),
            ("o2_b1s1_v",       "O2 B1S1",             "V"),
            ("intake_temp_c",   "Temp. admissão",      "°C"),
            ("mileage_km",      "Odômetro do frame",   "km"),
        ]
        rows = []
        for key, label, unit in pairs:
            v = ff.get(key)
            if v in (None, ""):
                continue
            if unit == "%":
                txt = f"{v:.1f}" if isinstance(v, float) else str(v)
            elif unit in ("°C", "km/h", "rpm", "km", "g/s", "V"):
                txt = f"{v:.1f}" if isinstance(v, float) and not float(v).is_integer() else str(v)
            else:
                txt = (
                    f"<code>{esc(v)}</code>"
                    if isinstance(v, str) and v.startswith(("P","C","B","U"))
                    else esc(v)
                )
            rows.append(
                "<tr>"
                f"<td class='small text-muted'>{esc(label)}</td>"
                f"<td class='small'>{txt} {esc(unit) if unit else ''}</td>"
                "</tr>"
            )
        if not rows:
            return ""
        return (
            "<div class='col-12'>"
            "<div class='card'>"
            "<div class='card-header small text-muted py-2'>"
            "❄ Freeze Frame — momento do DTC"
            "</div>"
            "<div class='card-body p-0'><div class='table-responsive'>"
            "<table class='table table-sm table-dark align-middle mb-0' style='max-width: 640px;'>"
            "<thead><tr><th>Parâmetro</th><th>Valor</th></tr></thead>"
            "<tbody>"
            + "".join(rows)
            + "</tbody></table></div></div></div></div>"
        )

    def readiness_block() -> str:
        rd = s.get("readiness") or {}
        if not isinstance(rd, dict) or not rd:
            return ""
        monitors = rd.get("monitors") or {}
        rows = []
        for name, done in monitors.items():
            state = (
                "<span class='text-success'>completo</span>"
                if done
                else "<span class='text-warning'>incompleto</span>"
            )
            rows.append(
                f"<tr><td class='small text-muted'>{esc(name)}</td>"
                f"<td class='small'>{state}</td></tr>"
            )
        extras = []
        if rd.get("distance_since_clear_km") is not None:
            extras.append(
                f"Distância desde a limpeza de DTCs: <b>{esc(rd['distance_since_clear_km'])} km</b>"
            )
        if rd.get("warmups_since_clear") is not None:
            extras.append(
                f"Ciclos de aquecimento desde a limpeza: <b>{esc(rd['warmups_since_clear'])}</b>"
            )
        assessment = rd.get("clear_assessment") or {}
        verdict_html = ""
        verdict = assessment.get("verdict")
        if verdict:
            cls = {"suspeito": "danger", "normal": "success", "inconclusivo": "warning"}.get(
                verdict, "secondary"
            )
            title = {
                "suspeito": "⚠ Indício de limpeza recente de códigos",
                "normal": "✓ Sem indício de limpeza recente",
                "inconclusivo": "? Verificação inconclusiva",
            }.get(verdict, verdict)
            evidence = "".join(f"<li>{esc(e)}</li>" for e in assessment.get("evidence", []))
            recommendation = assessment.get("recommendation") or ""
            verdict_html = (
                f"<div class='alert alert-{cls} small m-2 py-2'>"
                f"<b>{title}</b> "
                "<span class='text-muted'>"
                f"(confiança {esc(assessment.get('confidence', '—'))})</span>"
                + (f"<ul class='mb-1 mt-1 ps-3'>{evidence}</ul>" if evidence else "")
                + (f"<div class='mt-1'>{esc(recommendation)}</div>" if recommendation else "")
                + "</div>"
            )
        if not rows and not verdict_html:
            return ""
        table_html = (
            "<div class='table-responsive'>"
            "<table class='table table-sm table-dark align-middle mb-0' style='max-width: 640px;'>"
            "<thead><tr><th>Monitor</th><th>Ciclo</th></tr></thead>"
            f"<tbody>{''.join(rows)}</tbody></table></div>"
            if rows
            else ""
        )
        extras_html = (
            f"<div class='small text-muted px-2 pt-2'>{' · '.join(extras)}</div>" if extras else ""
        )
        return (
            "<div class='col-12'>"
            "<div class='card'>"
            "<div class='card-header small text-muted py-2'>"
            "🛡 Prontidão dos monitores (readiness) e verificação de limpeza de códigos"
            "</div>"
            f"<div class='card-body p-0'>{table_html}{extras_html}{verdict_html}</div>"
            "</div></div>"
        )

    def inspection_block() -> str:
        verdict = build_inspection_verdict(s)
        meta = {
            "aprovado": ("success", "✓"),
            "aprovado_com_ressalvas": ("warning", "△"),
            "reinspecionar": ("warning", "🔄"),
            "reprovado": ("danger", "✕"),
        }
        cls, icon = meta.get(verdict.verdict, ("secondary", "•"))
        reasons = "".join(f"<li>{esc(r)}</li>" for r in verdict.reasons)
        return (
            f"<div class='alert alert-{cls} py-3 mb-3'>"
            f"<div class='fw-bold fs-5 mb-1'>{icon} Parecer de vistoria: {esc(verdict.label)}</div>"
            + (f"<ul class='mb-1 ps-3 small'>{reasons}</ul>" if reasons else "")
            + f"<div class='small'>{esc(verdict.recommendation)}</div>"
            "<div class='small text-muted mt-1'>Parecer restrito ao diagnóstico eletrônico "
            "OBD2 (motor/emissões); não substitui inspeção mecânica e estrutural.</div>"
            "</div>"
        )

    comparison_html = ""
    if report.previous:
        comparison_html = (
            "<div class='col-12'>"
            "<div class='card'>"
            "<div class='card-header small text-muted py-2'>"
            "Comparação com sessão anterior"
            "</div>"
            f"<div class='card-body'>{delta_dtcs}</div>"
            "</div>"
            "</div>"
        )
    analysis_html = (
        "<div class='analysis-box'>" + esc(analysis) + "</div>"
        if analysis
        else "<div class='text-muted'>Sem análise IA.</div>"
    )
    vehicle_history_html = ""
    if vhist:
        rows = []
        for row in vhist:
            rid = row.get("id")
            active = "table-active" if rid == s.get("id") else ""
            urg = row.get("urgency") or "informativo"
            urg_kind = sev.get(urg, "secondary")
            dtcs = row.get("dtc_codes") or []
            dtcs_html = " ".join(f"<code>{esc(c)}</code>" for c in dtcs[:6]) or "—"
            if len(dtcs) > 6:
                dtcs_html += f" <span class='text-muted'>+{len(dtcs) - 6}</span>"
            rows.append(
                "<tr class='" + active + "'>"
                f"<td class='small text-muted'>#{esc(rid)}</td>"
                f"<td class='small'>{esc(row.get('ts'))}</td>"
                f"<td>{badge(urg, urg_kind)}</td>"
                f"<td class='small'>{dtcs_html}</td>"
                "<td class='text-end'>"
                f"<a class='btn btn-outline-secondary btn-sm' href='/report/{esc(rid)}' "
                "target='_blank'>Abrir</a>"
                f"<a class='btn btn-outline-secondary btn-sm ms-2' "
                f"href='/report/{esc(rid)}/download'>Baixar</a>"
                "</td>"
                "</tr>"
            )
        vehicle_history_html = (
            "<div class='col-12'>"
            "<div class='card'>"
            "<div class='card-header small text-muted py-2'>Histórico do veículo</div>"
            "<div class='card-body p-0'>"
            "<div class='table-responsive'>"
            "<table class='table table-sm table-dark align-middle mb-0'>"
            "<thead><tr><th>ID</th><th>Data</th><th>Urgência</th><th>DTCs</th><th></th></tr></thead>"
            "<tbody>"
            + "".join(rows)
            + "</tbody></table></div>"
            "</div></div></div>"
        )

    return f"""<!doctype html>
<html lang="pt-BR" data-bs-theme="dark">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>AutoDiag — Relatório #{esc(s.get('id'))}</title>
  <link
    href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css"
    rel="stylesheet"
  >
  <style>
    body {{ background: #0d1117; color: #e6edf3; }}
    .card {{ background: #161b22; border-color: #30363d; }}
    .table {{ color: #e6edf3; }}
    .table thead th {{
      color: #8b949e;
      font-weight: 500;
      font-size: 12px;
      text-transform: uppercase;
      border-color: #21262d;
    }}
    .table td {{ border-color: #21262d; }}
    .analysis-box {{
      white-space: pre-wrap;
      background: #010409;
      border: 1px solid #30363d;
      border-radius: 6px;
      padding: 16px;
    }}
    @media print {{
      .no-print {{ display:none !important; }}
      body {{ background: white; color: black; }}
    }}
  </style>
</head>
<body>
  <nav
    class="navbar px-4 py-3 no-print"
    style="background:#161b22;border-bottom:1px solid #30363d;"
  >
    <div class="d-flex align-items-center gap-2">
      <span class="fw-bold" style="color:#58a6ff;">◈ AutoDiag</span>
      <span class="text-muted">Relatório #{esc(s.get('id'))}</span>
      {badge(s.get("urgency") or "informativo", sev_cls)}
    </div>
    <div class="d-flex gap-2">
      <a class="btn btn-outline-secondary btn-sm" href="/report/{esc(sid)}/download">Baixar HTML</a>
      <a class="btn btn-outline-secondary btn-sm" href="/report/{esc(sid)}/pdf">📄 PDF</a>
      <button class="btn btn-outline-secondary btn-sm" onclick="window.print()">Imprimir</button>
    </div>
  </nav>

  <div class="container-fluid px-4 py-4" style="max-width: 1200px;">
    {branding_block()}
    <div class="mb-3">
      <h2 class="h4 mb-1">{esc(s.get("vehicle_label") or "Veículo")}</h2>
      <div class="text-muted small">Data: {esc(s.get("ts"))} · VIN: {esc(s.get("vin") or "—")}</div>
    </div>

    {inspection_block()}

    <div class="row">
      {kpi("Urgência", badge(s.get("urgency") or "informativo", sev_cls))}
      {kpi("DTCs", esc(len(s.get("dtc_codes") or [])))}
      {kpi("KM", esc(s.get("km") or "—"))}
      {kpi("Orientação", badge((triage.get("drive_advice") or "—").upper(), "secondary"))}
    </div>

    <div class="row g-3">
      <div class="col-12">
        <div class="card">
          <div class="card-header small text-muted py-2">Triagem guiada</div>
          <div class="card-body">{triage_block()}</div>
        </div>
      </div>

      <div class="col-12">
        <div class="card">
          <div class="card-header small text-muted py-2">DTCs</div>
          <div class="card-body p-0">{dtc_table(report.dtcs)}</div>
        </div>
      </div>

      {vehicle_history_html}

      {comparison_html}

      {freeze_frame_block()}
      {readiness_block()}
      {cost_block()}

      <div class="col-12">
        <div class="card">
          <div class="card-header small text-muted py-2">Análise IA (opcional)</div>
          <div class="card-body">
            {analysis_html}
          </div>
        </div>
      </div>

      {notes_block()}
      {qr_block()}
    </div>
  </div>
</body>
</html>"""
