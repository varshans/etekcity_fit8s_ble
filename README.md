# Etekcity Fit 8S / ESF-551 BLE

This package provides a basic unofficial interface for interacting with **Etekcity Fit 8S** and ESF-551 Smart Fitness Scale using Bluetooth Low Energy (BLE).

It lets you:

- Receive **weight** and **impedance** measurements.
- Work in either **GATT connect mode** or **advertisement-only mode** (no pairing required for FIT 8S).
- Manage the display unit setting.
- Calculate various **body metrics** (BMI, BFP, muscle mass, water %, metabolic age, etc.).

It has been tested on the **Fit 8S / ESF-551**. Other models may or may not work. If you try it with a different Etekcity scale, feedback is welcome.

**Disclaimer**: This is an unofficial, community-developed library. It is not affiliated with, officially maintained by, or in any way officially connected with Etekcity, VeSync Co., Ltd. (the owner of the Etekcity brand), or any of their subsidiaries or affiliates. The official Etekcity website can be found at [etekcity.com](https://www.etekcity.com), and the official VeSync website at [vesync.com](https://www.vesync.com). The names "Etekcity" and "VeSync" as well as related marks are registered trademarks of their respective owners.

---

## Installation

```bash
pip install etekcity_fit8s_ble
```

---

## Quick Start

### Classic GATT mode (connect + notify)

```python
import asyncio
from etekcity_fit8s_ble import (
    IMPEDANCE_KEY, WEIGHT_KEY,
    EtekcitySmartFitnessScale, ScaleData, WeightUnit,
    BodyMetrics, Sex,
)

async def main():
    def on_data(data: ScaleData):
        print(f"Weight: {data.measurements[WEIGHT_KEY]} kg")
        if IMPEDANCE_KEY in data.measurements:
            print(f"Impedance: {data.measurements[IMPEDANCE_KEY]} Ω")
            # Add body metrics
            metrics = BodyMetrics(
                weight_kg=data.measurements[WEIGHT_KEY],
                height_m=1.75,
                age=30,
                sex=Sex.Male,
                impedance=data.measurements[IMPEDANCE_KEY],
            )
            print("Body Fat %:", metrics.body_fat_percentage)

    scale = EtekcitySmartFitnessScale("AA:BB:CC:DD:EE:FF", on_data)
    scale.display_unit = WeightUnit.KG
    await scale.async_start()
    await asyncio.sleep(30)
    await scale.async_stop()

asyncio.run(main())
```

### Advertisement-only mode (no connect for FIT 8S)

```python
import asyncio
from datetime import date

from etekcity_fit8s_ble import (
    EtekcitySmartFitnessScaleWithBodyMetrics,
    Sex,
    WeightUnit,
)


def on_data(scale_data):
    print("ADV Weight (kg):", scale_data.measurements.get("weight"))
    print("Impedance (ohm):", scale_data.measurements.get("impedance"))
    print("Body Fat %:", scale_data.measurements.get("body_fat_percentage"))


async def main():
    scale = EtekcitySmartFitnessScaleWithBodyMetrics(
        notification_callback=on_data,
        sex=Sex.Male,
        birthdate=date(1990, 1, 1),
        height_m=1.80,
        display_unit=WeightUnit.KG,
        use_advertisements=True,   # ADV mode (no GATT connect)
    )

    await scale.async_start()
    print("Listening… step on the scale. Press Ctrl+C to stop.")

    try:
        while True:
                await asyncio.sleep(1)

    except KeyboardInterrupt:
        pass
    finally:
        await scale.async_stop()
        print("Stopped.")


if __name__ == "__main__":
    asyncio.run(main())
```

---

## API Reference

### `EtekcitySmartFitnessScale`

- `__init__(address, notification_callback, display_unit=None, ...)`
- `async_start()` / `async_stop()`

### `EtekcitySmartFitnessScaleWithBodyMetrics`

- Same as above, but requires `sex`, `birthdate`, and `height_m`.
- Adds automatic body composition calculations.
- New optional `use_advertisements: bool` flag to read directly from broadcast frames.

### `WeightUnit`

- `WeightUnit.KG`, `WeightUnit.LB`, `WeightUnit.ST`

### `ScaleData`

- `name`, `address`, `hw_version`, `sw_version`, `display_unit`, `measurements`

### `BodyMetrics`

Calculates BMI, body fat %, fat-free weight, subcutaneous fat, visceral fat value, body water %, BMR, skeletal muscle %, muscle mass, bone mass, protein %, scores, and metabolic age.

### `Sex`

- `Sex.Male`, `Sex.Female`

---

## Compatibility

- Verified on **Fit 8S / ESF-551**
- Works on macOS (CoreBluetooth) and Linux (BlueZ, e.g. Raspberry Pi 4).
- Windows support is untested.

---

## Troubleshooting

On Raspberry Pi / BlueZ, if you hit `org.bluez.Error.InProgress`:

```bash
bluetoothctl
power off
power on
scan on
```

---

## Support

If this helped you integrate your Fit 8S scale, consider supporting the original project maintainer:  
[![Buy Me A Coffee](https://www.buymeacoffee.com/assets/img/custom_images/orange_img.png)](https://www.buymeacoffee.com/ronnnnnnn)

---

## License

MIT License – see [LICENSE](LICENSE).
