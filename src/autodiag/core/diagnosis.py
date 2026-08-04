from autodiag.elm327.reader import DTCRecord, LivePIDs

CRITICAL_DTCS = {
    "P0300", "P0301", "P0302", "P0303", "P0304",
    "P0700", "P0740", "P0730", "P0741",
    "U0100", "U0001", "B0001", "B0002", "B1001", "C0900",
}

ATTENTION_DTCS = {
    "P0101", "P0171", "P0172", "P0174", "P0175",
    "P0401", "P0506", "P0507", "U0121", "P0420", "P0430",
}


def infer_urgency(dtcs: list[DTCRecord], pids: LivePIDs) -> str:
    codes = {d.code for d in dtcs}
    if codes & CRITICAL_DTCS:
        return "critico"
    if pids.coolant_temp_c is not None and pids.coolant_temp_c > 108:
        return "critico"
    if codes & ATTENTION_DTCS:
        return "atencao"
    if pids.fuel_trim_short_b1 is not None and abs(pids.fuel_trim_short_b1) > 15:
        return "atencao"
    if pids.maf_g_s is not None and pids.maf_g_s < 2.0:
        return "atencao"
    if dtcs:
        return "atencao"
    return "informativo"
