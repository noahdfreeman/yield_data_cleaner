# QGIS Compatibility & Environment Report

Yield Data Cleaner is engineered for broad compatibility across QGIS Long Term Release (LTR) distributions and modern operating systems.

---

## Supported QGIS & Python Versions

| Component | Minimum Version | Recommended Version | Maximum Tested |
| :--- | :--- | :--- | :--- |
| **QGIS Desktop** | **3.28 LTR (Firenze)** | **3.34 LTR (Prizren)** / **3.40 LTR** | **3.44+ / 4.99 dev** |
| **Python** | **3.9+** | **3.11 / 3.12** | **3.14** |
| **Qt / PyQt** | **PyQt5 (Qt 5.15+)** | **PyQt5 / PyQt6** | **PyQt6 (Qt 6.x)** |

---

## Operating System Matrix

| Operating System | Supported | Architecture | Notes |
| :--- | :---: | :---: | :--- |
| **Microsoft Windows** | Yes | x86_64, ARM64 | Tested on Windows 10 & 11 via OSGeo4W and standalone installers. |
| **macOS** | Yes | Apple Silicon (M1/M2/M3), Intel | Tested on macOS 13+ (Ventura, Sonoma, Sequoia) via official QGIS DMG. |
| **Linux** | Yes | x86_64, aarch64 | Tested on Ubuntu 22.04 / 24.04 LTS, Debian, Fedora. |

---

## Dependency Architecture

- **Zero Heavy External Dependencies**: Yield Data Cleaner uses standard library Python and native PyQGIS (`qgis.core`, `qgis.gui`, `PyQt5`/`PyQt6`).
- **No C-extensions Required**: Operates out of the box on any standard QGIS installation without needing `pip install` or compiler tools.
- **Offline Capable**: Core algorithms, dialogs, map previews, and calculations run 100% offline.
