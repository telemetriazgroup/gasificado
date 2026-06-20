import json
from dataclasses import dataclass, asdict

DEFAULT_CONFIG = {
    "gas_divisor": 10,
    "gas_low_max_ppm": 1000,
    "gas_low_display_max": 100.0,
    "gas_mid_min_ppm": 1000,
    "gas_mid_max_ppm": 2000,
    "gas_mid_display_min": 100.0,
    "gas_mid_display_max": 110.9,
    "gas_high_display": 120.1,
    "temp_raw_max": 800,
    "temp_display_cap": 80.1,
    "use_manual_override": False,
    "manual_gas_display": None,
    "manual_temp_display": None,
}


@dataclass
class DisplayRules:
    gas_divisor: float = 10
    gas_low_max_ppm: int = 1000
    gas_low_display_max: float = 100.0
    gas_mid_min_ppm: int = 1000
    gas_mid_max_ppm: int = 2000
    gas_mid_display_min: float = 100.0
    gas_mid_display_max: float = 110.9
    gas_high_display: float = 120.1
    temp_raw_max: int = 800
    temp_display_cap: float = 80.1
    use_manual_override: bool = False
    manual_gas_display: float | None = None
    manual_temp_display: float | None = None

    @classmethod
    def from_dict(cls, data: dict) -> "DisplayRules":
        merged = {**DEFAULT_CONFIG, **(data or {})}
        return cls(**{k: merged[k] for k in cls.__dataclass_fields__})

    def to_dict(self) -> dict:
        return asdict(self)


def transform_gas_ppm(raw_ppm: int | None, rules: DisplayRules) -> float | None:
    if raw_ppm is None:
        return None
    if rules.use_manual_override and rules.manual_gas_display is not None:
        return float(rules.manual_gas_display)

    if raw_ppm < rules.gas_low_max_ppm:
        return min(raw_ppm / rules.gas_divisor, rules.gas_low_display_max)
    if raw_ppm <= rules.gas_mid_max_ppm:
        span = rules.gas_mid_max_ppm - rules.gas_mid_min_ppm
        if span <= 0:
            return rules.gas_mid_display_max
        ratio = (raw_ppm - rules.gas_mid_min_ppm) / span
        return rules.gas_mid_display_min + ratio * (
            rules.gas_mid_display_max - rules.gas_mid_display_min
        )
    return rules.gas_high_display


def transform_temperature(temp_celsius: float | None, rules: DisplayRules) -> float | None:
    if temp_celsius is None:
        return None
    if rules.use_manual_override and rules.manual_temp_display is not None:
        return float(rules.manual_temp_display)

    raw_sensor = temp_celsius * 10
    if raw_sensor > rules.temp_raw_max:
        return rules.temp_display_cap
    return temp_celsius


def apply_client_sensor_values(
    temperature: float | None,
    gas_ppm: int | None,
    rules: DisplayRules,
) -> tuple[float | None, float | None]:
    return (
        transform_temperature(temperature, rules),
        transform_gas_ppm(gas_ppm, rules),
    )
