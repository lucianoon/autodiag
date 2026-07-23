from dataclasses import dataclass

import httpx

_VIN_YEAR: dict[str, int] = {
    "F": 2015, "G": 2016, "H": 2017, "J": 2018, "K": 2019,
    "L": 2020, "M": 2021, "N": 2022, "P": 2023, "R": 2024,
    "S": 2025, "T": 2026,
}

_WMI: dict[str, str] = {
    "9BW": "Volkswagen Brasil", "9BF": "Ford Brasil", "9BD": "GM Brasil",
    "9BS": "Fiat Brasil", "9BH": "Honda Brasil", "9BM": "Mercedes-Benz Brasil",
    "9BR": "Toyota Brasil", "9BJ": "Renault Brasil", "93H": "Honda Brasil",
    "93Y": "Toyota Brasil", "VF7": "Citroën", "VF3": "Peugeot",
    "WBA": "BMW", "WVW": "Volkswagen Alemanha", "1HG": "Honda EUA",
    "1G1": "GM EUA", "2T1": "Toyota Canadá", "3VW": "VW México",
    "8AF": "Ford Argentina", "8A1": "GM Argentina",
}


@dataclass
class VehicleProfile:
    vin: str = ""
    make: str = ""
    model: str = ""
    year: int = 0
    engine: str = ""
    fuel: str = ""
    transmission: str = ""
    country: str = ""

    @property
    def label(self) -> str:
        parts = [p for p in [self.make, self.model, str(self.year) if self.year else ""] if p]
        return " ".join(parts) or "Veículo desconhecido"


def decode_vin_local(vin: str) -> VehicleProfile:
    vin = vin.upper().strip()
    profile = VehicleProfile(vin=vin)
    if len(vin) != 17:
        return profile
    profile.make = _WMI.get(vin[:3], f"WMI:{vin[:3]}")
    year_char = vin[9]
    profile.year = _VIN_YEAR.get(year_char, 0)
    return profile


async def decode_vin_nhtsa(vin: str) -> VehicleProfile:
    profile = decode_vin_local(vin)
    if len(vin) != 17:
        return profile
    try:
        url = f"https://vpic.nhtsa.dot.gov/api/vehicles/DecodeVinValues/{vin}?format=json"
        async with httpx.AsyncClient(timeout=8.0) as client:
            r = await client.get(url)
            r.raise_for_status()
            results = r.json().get("Results", [{}])[0]
        profile.make = results.get("Make") or profile.make
        profile.model = results.get("Model") or ""
        year_str = results.get("ModelYear") or ""
        if year_str.isdigit():
            profile.year = int(year_str)
        profile.engine = results.get("DisplacementL") or ""
        fuel = results.get("FuelTypePrimary") or ""
        profile.fuel = fuel
        profile.country = results.get("PlantCountry") or ""
    except Exception:
        pass
    return profile
