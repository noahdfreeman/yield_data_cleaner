# Privacy & Data Security

Yield Data Cleaner is designed with a strict **Local-First, Privacy-Preserving** architecture. Your farm, field, and yield telemetry data are your private assets.

---

## Privacy Guarantees

1. **100% Local Execution**: All data ingestion, column mapping, pass reconstruction, filtering algorithms, and export routines run entirely on your local machine.
2. **No Data Uploads**: Yield Data Cleaner does not transmit your yield data, coordinates, farm names, or machine telemetry to any remote server or cloud provider.
3. **No Telemetry / Analytics**: The plugin contains no tracking beacons, usage analytics, telemetry pings, or third-party advertising SDKs.
4. **Online Basemap Disclosures**:
   - The standalone HTML review report includes optional satellite and street basemaps provided by Esri Tile Services.
   - When viewing the HTML review with an active internet connection, your web browser requests map tiles for the visible bounding box. No attribute data, yield numbers, or farm metadata are sent with these tile requests.
   - The HTML review report can be viewed fully offline if an internet connection is not available.

---

## Software Security Practices

- **Zero Bundled Binaries**: The plugin contains no compiled `.dll`, `.exe`, `.so`, or ActiveX (`.ocx`) legacy binaries.
- **Input Sanitization & Escaping**: All file paths, field names, and column headers are escaped before rendering in the HTML review report to prevent script injection.
- **Path Traversal Protection**: Output folder paths and export destinations are strictly validated against filesystem boundaries.
- **Release Verification**: Every distributed release ZIP is validated with automated security checksums and archive linters before publication.
