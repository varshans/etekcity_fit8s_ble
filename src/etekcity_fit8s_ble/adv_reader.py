from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Callable, Optional

from bleak import BleakScanner

from .const import WEIGHT_KEY, IMPEDANCE_KEY

_LOGGER = logging.getLogger(__name__)

# Etekcity / Vesync company ID in ManufacturerData
_MFR_ID = 0x06D0
# Optional for robustness.
_SERVICE_UUID_FFD0 = "0000ffd0-0000-1000-8000-00805f9b34fb"


@dataclass(frozen=True)
class AdvReading:
    address: str
    mac_in_frame: Optional[str]
    rssi: Optional[int]
    weight_kg: Optional[float]
    impedance_ohm: Optional[int]
    stable: bool
    ts: float
    raw_hex: str


def _parse_mfr_06d0(payload: bytes) -> dict[str, Optional[float | int | str]]:
    """
    Fit 8S 0x06D0 (20 bytes) parser.

    [0]      : 0x01
    [1..6]   : reversed MAC
    [7..9]   : C0 A8 01
    [10..12] : weight grams (LE24)
    [13..14] : impedance ohms (LE16), 0 -> missing
    [15..19] : flags (5 bytes)
    """
    out = {"mac": None, WEIGHT_KEY: None, IMPEDANCE_KEY: None, "raw_hex": payload.hex()}
    if len(payload) != 20 or payload[0] != 0x01:
        return out

    mac_rev = payload[1:7]
    out["mac"] = ":".join(f"{b:02X}" for b in mac_rev[::-1])

    grams = payload[10] | (payload[11] << 8) | (payload[12] << 16)
    if grams > 0:
        out[WEIGHT_KEY] = round(grams / 1000.0, 3)

    imp = payload[13] | (payload[14] << 8)
    if imp != 0:
        out[IMPEDANCE_KEY] = imp

    return out


def _adv_has_service(device, adv, *, require_service: bool) -> bool:
    if not require_service:
        return True
    if _SERVICE_UUID_FFD0 in (adv.service_uuids or []):
        return True
    # BlueZ fallback: device.details['props']['UUIDs']
    details = getattr(device, "details", None)
    if isinstance(details, dict):
        uuids = (details.get("props", {}) or {}).get("UUIDs", []) or []
        return _SERVICE_UUID_FFD0 in uuids
    return False


def _norm_mac(s: str | None) -> str | None:
    if not s:
        return None
    return s.replace("-", ":").replace(".", ":").upper()


def _quantize_weight(w: float, step: float) -> float:
    # Round to nearest step (e.g., 0.02 kg) for stable repeat counting & change detection
    return round(round(w / step) * step, 3)


async def listen_advertisements(
    on_reading: Callable[[AdvReading], None],
    *,
    require_service: bool = False,
    stable_repeats: int = 10,
    min_delta_kg: float = 0.02,
    address_filter: Optional[str] = None,
    weight_epsilon_kg: float = 0.02,
    emit_transients: bool = False,
    min_emit_interval_s: float = 1.0,
) -> None:
    """
    Stream `AdvReading` objects from advertisements (no GATT connection).

    Args:
        on_reading: callback invoked when a reading changes or becomes stable
        require_service: if True, also require FFD0 service in the ADV
        stable_repeats: mark stable after N near-identical readings (or when impedance appears)
        min_delta_kg: minimum delta vs last *emitted* weight to emit another transient reading
        address_filter: if provided, only consider this device address (case-insensitive).
                        Matches either OS-reported address OR MAC embedded in payload.
                        If not provided, fall back to filtering by ManufacturerData (0x06D0).
        weight_epsilon_kg: tolerance for repeat detection / quantization (jitter smoothing)
        emit_transients: if False (default), only emit when `stable` is True
                         (impedance present or repeats >= stable_repeats).
                         If True, emit transient changes too (rate-limited & thresholded).
        min_emit_interval_s: cooldown between emissions per device

    This function never returns unless cancelled.
    """
    last_seen_q: dict[str, float] = {}       # last quantized *seen* weight per addr
    repeat_count: dict[str, int] = {}        # count of consecutive near-identical frames
    last_emit_ts: dict[str, float] = {}      # last time we emitted for addr
    last_emit_q: dict[str, float] = {}       # last quantized *emitted* weight per addr

    addr_filter_norm = _norm_mac(address_filter)

    def _should_consider_device(device, parsed_mac: Optional[str]) -> bool:
        """If address_filter is set, accept if device.address OR parsed MAC matches it."""
        if not addr_filter_norm:
            return True
        dev_addr = _norm_mac(getattr(device, "address", None))
        parsed_addr = _norm_mac(parsed_mac)
        return (dev_addr == addr_filter_norm) or (parsed_addr == addr_filter_norm)

    def _on_detect(device, adv) -> None:
        # If no address filter: require manufacturer/company ID 0x06D0 (and optional service).
        # If address filter is set: still require manufacturer payload to parse readings.
        mfr = adv.manufacturer_data or {}
        payload = mfr.get(_MFR_ID)
        if not payload:
            return
        if not _adv_has_service(device, adv, require_service=require_service):
            return

        parsed = _parse_mfr_06d0(payload)
        if not _should_consider_device(device, parsed.get("mac")):
            return

        weight = parsed.get(WEIGHT_KEY)
        imp = parsed.get(IMPEDANCE_KEY)
        if weight is None:
            return

        addr = getattr(device, "address", None) or parsed.get("mac") or ""
        wq = _quantize_weight(weight, weight_epsilon_kg)

        # Repeat counting (near-identical within epsilon)
        prev_q = last_seen_q.get(addr)
        if prev_q is None or abs(wq - prev_q) > (weight_epsilon_kg / 2):
            last_seen_q[addr] = wq
            repeat_count[addr] = 1
        else:
            repeat_count[addr] = repeat_count.get(addr, 1) + 1

        # Stability decision: either impedance is present, or enough repeats at the same quantized weight
        stable = (imp is not None) or (repeat_count.get(addr, 0) >= stable_repeats)

        # Rate limiting (cooldown) vs last emitted
        now = time.time()
        last_ts = last_emit_ts.get(addr, 0.0)
        last_q = last_emit_q.get(addr)

        def _emit_allowed_transient() -> bool:
            if not emit_transients:
                return False
            if (now - last_ts) < min_emit_interval_s:
                return False
            if last_q is None:
                return True
            return abs(wq - last_q) >= min_delta_kg

        # Emit policy:
        #   - Always allow one emit when 'stable' transitions true (or changes to a new stable value).
        #   - Otherwise (transients) emit only if enabled & surpassed delta and cooldown.
        do_emit = False
        if stable:
            if (last_q is None) or (abs(wq - last_q) > (weight_epsilon_kg / 2)) or ((now - last_ts) >= min_emit_interval_s):
                do_emit = True
        else:
            do_emit = _emit_allowed_transient()

        if not do_emit:
            return

        last_emit_ts[addr] = now
        last_emit_q[addr] = wq

        reading = AdvReading(
            address=addr,
            mac_in_frame=parsed.get("mac"),
            rssi=adv.rssi,
            weight_kg=weight,        # unquantized value to caller
            impedance_ohm=imp,
            stable=bool(stable),
            ts=now,
            raw_hex=parsed.get("raw_hex", ""),
        )
        try:
            on_reading(reading)
        except Exception:
            _LOGGER.exception("on_reading callback raised")

    scanner = BleakScanner(
        detection_callback=_on_detect,
        scanning_mode="active",
        service_uuids=None,
    )
    await scanner.start()
    _LOGGER.debug(
        "Advertisement listener started (require_service=%s, address_filter=%s, epsilon=%.3f, stable_repeats=%d, emit_transients=%s, min_emit_interval_s=%.2f)",
        require_service, addr_filter_norm, weight_epsilon_kg, stable_repeats, emit_transients, min_emit_interval_s
    )
    try:
        while True:
            await asyncio.sleep(1)
    finally:
        await scanner.stop()
        _LOGGER.debug("Advertisement listener stopped.")
