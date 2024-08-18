# Etekcity ESF551 BLE

This Python package provides an interface for interacting with Etekcity ESF551 Smart Fitness Scales using Bluetooth Low Energy (BLE).

## Installation

You can install the package using pip:

```
pip install etekcity_esf551_ble
```

## Usage

Here's a basic example of how to use the package:

```python
from etekcity_esf551_ble import EtekcitySmartFitnessScale

def callback(scale_data):
    print(f"Weight: {scale_data.measurements['weight']} kg")

scale = EtekcitySmartFitnessScale("00:11:22:33:44:55", callback)
await scale.async_start()
# ... wait for measurements ...
await scale.async_stop()
```

Replace "00:11:22:33:44:55" with the actual Bluetooth address of your scale.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.
