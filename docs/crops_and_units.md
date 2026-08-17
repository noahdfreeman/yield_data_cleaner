# Crop Profiles & Unit Systems

Yield calculations and biological range checks depend heavily on crop-specific physical properties, market moisture standards, and standard test weights.

---

## Supported Crop Profiles

Yield Data Cleaner includes built-in agronomic profiles for standard field crops:

| Crop Profile | Code | Standard Market Moisture (%) | Standard Test Weight (lb/bu) | Metric Equivalent (kg/hL) | Typical Yield Range (bu/ac) |
| :--- | :--- | :---: | :---: | :---: | :---: |
| **Corn (Maize)** | `corn` | **15.5%** | **56.0 lb/bu** | 72.08 kg/hL | 50 – 350 |
| **Soybean** | `soybean` | **13.0%** | **60.0 lb/bu** | 77.23 kg/hL | 15 – 110 |
| **Wheat (All types)**| `wheat` | **13.5%** | **60.0 lb/bu** | 77.23 kg/hL | 20 – 140 |
| **Barley** | `barley` | **14.5%** | **48.0 lb/bu** | 61.78 kg/hL | 30 – 160 |
| **Oats** | `oats` | **14.0%** | **32.0 lb/bu** | 41.19 kg/hL | 40 – 180 |
| **Sorghum / Milo** | `sorghum` | **14.0%** | **56.0 lb/bu** | 72.08 kg/hL | 30 – 180 |
| **Canola / Rapeseed**| `canola` | **10.0%** | **50.0 lb/bu** | 64.36 kg/hL | 15 – 90 |
| **Sunflower** | `sunflower` | **10.0%** | **28.0 lb/bu** | 36.04 kg/hL | 500 – 3500 (lb/ac) |

---

## Moisture Adjustment Mathematics

Raw grain mass contains variable moisture that must be normalized to standard commercial base moisture:

$$\text{Moisture Multiplier} = \frac{100 - \text{Harvest Moisture (\%)}}{100 - \text{Standard Market Moisture (\%)}}$$

$$\text{Dry Mass} = \text{Wet Mass} \times \text{Moisture Multiplier}$$

---

## Unit Systems & Conversion Reference

Yield Data Cleaner supports seamless bidirectional conversion between **Imperial (US Customary)** and **Metric (SI)** units:

### Yield Measurements
- $1\text{ bu/ac (corn, 56 lb/bu)} = 0.06277\text{ t/ha} = 62.77\text{ kg/ha}$
- $1\text{ bu/ac (soybean/wheat, 60 lb/bu)} = 0.06725\text{ t/ha} = 67.25\text{ kg/ha}$
- $1\text{ t/ha} = 1000\text{ kg/ha} = 15.93\text{ bu/ac (corn)} = 14.87\text{ bu/ac (soybean)}$

### Distance, Speed & Swath Width
- $1\text{ mph} = 1.60934\text{ km/h} = 1.46667\text{ ft/s} = 0.44704\text{ m/s}$
- $1\text{ ft} = 0.3048\text{ m} = 12\text{ in}$
- $1\text{ m} = 3.28084\text{ ft} = 39.37\text{ in}$

### Area & Mass
- $1\text{ acre} = 43,560\text{ sq ft} = 0.404686\text{ ha}$
- $1\text{ hectare} = 10,000\text{ sq m} = 2.47105\text{ acres}$
- $1\text{ lb} = 0.453592\text{ kg}$
- $1\text{ metric ton (t)} = 1,000\text{ kg} = 2,204.62\text{ lb}$
