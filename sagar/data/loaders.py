"""Adapters for real data, so the pipeline can be pointed at operational
sources without touching the algorithms.

Everything downstream depends on exactly two contracts:

  * a `Scene` (see `sagar.core.sarsim`)- sigma0 in dB plus a pixel->lat/lon
    mapping;
  * an ocean object exposing `sample_xy(t, x, y) -> (u, v, u_wind, v_wind)`.

Satisfy those two and the detector, the inversion and the attribution stage all
work unchanged. `SyntheticOcean` and the scene simulator are just the offline
implementations of the same contracts.

Optional dependencies are imported lazily and each raises an actionable message
if absent, so the core prototype stays install-free.
"""
from __future__ import annotations

import os

import numpy as np

from ..core.geoutil import Origin
from ..core.sarsim import Scene, SceneSpec


def _infer_truth_path(image_path: str):
    """Guess the mask companion for a Zenodo image (IMG_..._oil.tif ↔ mask)."""
    import glob as _glob
    base = os.path.splitext(image_path)[0]
    for cand in (base.replace("image", "mask"), base + "_mask", base + "_GT",
                 os.path.join(os.path.dirname(image_path), "masks", os.path.basename(image_path)),
                 image_path.replace(".tif", "_mask.tif"), image_path.replace(".tif", "_GT.tif")):
        if os.path.exists(cand):
            return cand
    # Scan dir for a mask file with same stem
    stem = os.path.splitext(os.path.basename(image_path))[0]
    for pat in (f"{stem}*mask*", f"{stem}*GT*", f"mask*{stem}*"):
        for m in _glob.glob(os.path.join(os.path.dirname(image_path), pat)):
            if os.path.exists(m):
                return m
    return None


def load_zenodo_tiff(path, origin: Origin, pixel_m=10.0, epoch=0.0, looks=4.4,
                     truth_path=None, band=0, auto_mask=True):
    """Load one image from the Zenodo Sentinel-1 oil-spill dataset.

    That dataset ships 2048x2048x2 Sigma0 TIFFs in dB with matching 2048x2048
    ground-truth masks:
      Part I   https://zenodo.org/records/8346860   (train)
      Part II  https://zenodo.org/records/8253899
      Part III https://zenodo.org/records/13761290  (test: oil / look-alike / clean)

    `origin` is the scene-centre geolocation- take it from the GRD product's
    metadata, or from the GeoTIFF's own geotransform if it carries one.

    Robustness: tries rasterio first (preserves georeference + 2-band handling),
    falls back to Pillow. Handles uint16 scaling and already-dB vs linear.
    """
    arr = None
    inferred_truth = None
    # Try rasterio path first if available (more faithful for 2-band + geotiff)
    if os.path.exists(path):
        try:
            import rasterio  # type: ignore
            with rasterio.open(path) as ds:
                # Heuristic: if 2 bands, band 0 is VV in dB per Zenodo docs
                b = band + 1
                if ds.count >= b:
                    arr = ds.read(b).astype(np.float32)
                    # Derive pixel spacing + origin from geotransform if GeoTIFF has one
                    if ds.transform and abs(ds.transform.a) > 1e-9:
                        try:
                            from rasterio.warp import transform as _warp
                            xs, ys = ds.xy(ds.height // 2, ds.width // 2)
                            if ds.crs and ds.crs.to_epsg() != 4326:
                                lon, lat = _warp(ds.crs, "EPSG:4326", [xs], [ys])
                                origin = Origin(float(lat[0]), float(lon[0]))
                            else:
                                origin = Origin(float(ys), float(xs)) if abs(xs) > 90 else Origin(float(lat) if 'lat' in locals() else origin.lat, float(lon) if 'lon' in locals() else origin.lon)
                            pixel_m = abs(ds.transform.a) if ds.crs and ds.crs.to_epsg() != 4326 else abs(ds.transform.a) * 111320.0
                        except Exception:
                            pass
                else:
                    arr = None
        except Exception:
            arr = None

    if arr is None:
        try:
            from PIL import Image
        except ImportError as e:                       # pragma: no cover
            raise RuntimeError("pillow is required to read TIFFs: pip install pillow") from e
        img = Image.open(path)
        # Pillow may open multi-frame TIFF as sequence; read first frame
        try:
            img.seek(0)
        except Exception:
            pass
        arr = np.array(img, dtype=np.float32)
        if arr.ndim == 3:
            # Zenodo 2048×2048×2: last dim is band
            if arr.shape[2] <= 4:
                arr = arr[..., min(band, arr.shape[2]-1)]
            else:
                arr = arr[..., band] if arr.shape[0] <= 4 else arr[..., band]
        # Handle the case where PIL returns (bands, H, W)
        if arr.ndim == 3 and arr.shape[0] <= 4:
            arr = arr[min(band, arr.shape[0]-1)]

    # Normalise dtype: if uint16-like values (>60) assume linear amplitude and convert
    if arr is not None and arr.size:
        # Detect dB vs linear: dB typically -35..+5, linear 0..~2
        # If max > 60, it's raw DN/amplitude squared
        try:
            mx = float(np.nanmax(arr))
            mn = float(np.nanmin(arr))
            if mx > 60 or (mn >= 0 and mx < 20 and np.median(arr) > 5):
                # Likely amplitude or power- convert to dB if needed
                # If clearly linear power (small values), convert
                if mx < 20:
                    arr = 10.0 * np.log10(np.clip(arr.astype(np.float64), 1e-9, None))
                else:
                    arr = 10.0 * np.log10(np.clip(arr.astype(np.float64) ** 2, 1e-9, None))
            # Clamp very negative dB to sensor floor
            arr = np.clip(arr, -45.0, 10.0)
        except Exception:
            pass

    if arr is None or arr.size == 0:
        raise RuntimeError(f"could not read image at {path}")

    n = min(arr.shape)
    arr = arr[:n, :n].astype(np.float32)

    # Truth mask
    tp = truth_path or (auto_mask and _infer_truth_path(path))
    truth = np.zeros(arr.shape, bool)
    if tp and os.path.exists(tp):
        try:
            from PIL import Image as _PIL
            t = np.array(_PIL.open(tp))
            if t.ndim == 3:
                t = t[..., 0]
            truth = (t[:n, :n] > 0)
        except Exception:
            try:
                import rasterio as _rio
                with _rio.open(tp) as _ds:
                    t = _ds.read(1)
                    truth = (t[:n, :n] > 0)
            except Exception:
                pass

    spec = SceneSpec(origin=origin, size=n, pixel_m=pixel_m, epoch=epoch, looks=looks)
    meta = dict(source=os.path.basename(path), truth_source=os.path.basename(tp) if tp and os.path.exists(tp) else None,
                data_mode=("REAL_IMAGERY" if truth.any() else "REAL_IMAGERY"))
    return Scene(sigma0_db=arr, truth_mask=truth, spec=spec, meta=meta)


def load_geotiff(path, epoch=0.0, looks=4.4, band=1):
    """Load a georeferenced Sentinel-1 GRD subset, deriving `origin` and the
    pixel spacing from the file's own geotransform. Requires rasterio."""
    try:
        import rasterio
    except ImportError as e:                       # pragma: no cover
        raise RuntimeError(
            "rasterio is required for georeferenced GeoTIFFs: pip install rasterio") from e

    with rasterio.open(path) as ds:
        arr = ds.read(band).astype(np.float32)
        if ds.crs and ds.crs.to_epsg() != 4326:
            from rasterio.warp import transform as warp_transform
            xs, ys = ds.xy(arr.shape[0] // 2, arr.shape[1] // 2)
            lon, lat = warp_transform(ds.crs, "EPSG:4326", [xs], [ys])
            origin = Origin(float(lat[0]), float(lon[0]))
            pixel_m = abs(ds.transform.a)
        else:
            lon, lat = ds.xy(arr.shape[0] // 2, arr.shape[1] // 2)
            origin = Origin(float(lat), float(lon))
            pixel_m = abs(ds.transform.a) * 111320.0

    # Amplitude/DN products need converting; a dB product is already log-scaled.
    if arr.max() > 60:
        arr = 10.0 * np.log10(np.clip(arr.astype(np.float64) ** 2, 1e-9, None))
    n = min(arr.shape)
    spec = SceneSpec(origin=origin, size=n, pixel_m=pixel_m, epoch=epoch, looks=looks)
    return Scene(sigma0_db=arr[:n, :n].astype(np.float32),
                 truth_mask=np.zeros((n, n), bool), spec=spec,
                 meta=dict(source=os.path.basename(path)))


class NetCDFOcean:
    """Metocean forcing from CMEMS currents + ERA5/CMEMS winds.

    Expects two NetCDF sources on a lat/lon/time grid:
      currents : CMEMS GLOBAL_ANALYSISFORECAST_PHY_001_024 (uo, vo at the surface)
      winds    : ERA5 single levels (u10, v10)

    Interpolation is trilinear in (time, lat, lon) and is done in the same local
    ENU frame the drift engine uses, so `sample_xy` is a drop-in replacement for
    `SyntheticOcean.sample_xy`.
    """

    def __init__(self, origin: Origin, currents_nc, winds_nc, epoch_np64,
                 cur_vars=("uo", "vo"), wind_vars=("u10", "v10")):
        try:
            import xarray as xr
        except ImportError as e:                   # pragma: no cover
            raise RuntimeError(
                "xarray + netcdf4 are required for NetCDF forcing: "
                "pip install xarray netcdf4") from e
        self.origin = origin
        self.cur = xr.open_dataset(currents_nc)
        self.wind = xr.open_dataset(winds_nc)
        self.epoch = np.datetime64(epoch_np64)
        self.cur_vars = cur_vars
        self.wind_vars = wind_vars

    def _interp(self, ds, names, t, lat, lon):
        import xarray as xr
        when = self.epoch + np.timedelta64(int(t), "s")
        la = xr.DataArray(np.ravel(lat), dims="p")
        lo = xr.DataArray(np.ravel(lon), dims="p")
        sel = ds[list(names)].interp(time=when, latitude=la, longitude=lo)
        out = [np.nan_to_num(np.asarray(sel[n].values), nan=0.0) for n in names]
        return [o.reshape(np.shape(lat)) for o in out]

    def sample_xy(self, t, x, y):
        lat, lon = self.origin.to_ll(x, y)
        u, v = self._interp(self.cur, self.cur_vars, t, lat, lon)
        uw, vw = self._interp(self.wind, self.wind_vars, t, lat, lon)
        return u, v, uw, vw

    def wind_field_xy(self, t, x, y):
        lat, lon = self.origin.to_ll(x, y)
        return self._interp(self.wind, self.wind_vars, t, lat, lon)

    def sample(self, t, lat, lon):
        from ..core.environment import Forcing
        x, y = self.origin.to_xy(lat, lon)
        u, v, uw, vw = self.sample_xy(t, np.array([x]), np.array([y]))
        return Forcing(float(u[0]), float(v[0]), float(uw[0]), float(vw[0]))
