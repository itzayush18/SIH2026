"""Adapters for real data, so the pipeline can be pointed at operational
sources without touching the algorithms.

Everything downstream depends on exactly two contracts:

  * a `Scene` (see `sagar.core.sarsim`) — sigma0 in dB plus a pixel->lat/lon
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


def load_zenodo_tiff(path, origin: Origin, pixel_m=10.0, epoch=0.0, looks=4.4,
                     truth_path=None, band=0):
    """Load one image from the Zenodo Sentinel-1 oil-spill dataset.

    That dataset ships 2048x2048x2 Sigma0 TIFFs in dB with matching 2048x2048
    ground-truth masks:
      Part I   https://zenodo.org/records/8346860   (train)
      Part II  https://zenodo.org/records/8253899
      Part III https://zenodo.org/records/13761290  (test: oil / look-alike / clean)

    `origin` is the scene-centre geolocation — take it from the GRD product's
    metadata, or from the GeoTIFF's own geotransform if it carries one.
    """
    try:
        from PIL import Image
    except ImportError as e:                       # pragma: no cover
        raise RuntimeError("pillow is required to read TIFFs: pip install pillow") from e

    img = Image.open(path)
    arr = np.array(img, dtype=np.float32)
    if arr.ndim == 3:
        arr = arr[..., band]
    n = min(arr.shape)
    arr = arr[:n, :n]

    truth = np.zeros(arr.shape, bool)
    if truth_path and os.path.exists(truth_path):
        t = np.array(Image.open(truth_path))
        truth = (t[:n, :n] > 0)

    spec = SceneSpec(origin=origin, size=n, pixel_m=pixel_m, epoch=epoch, looks=looks)
    return Scene(sigma0_db=arr, truth_mask=truth, spec=spec,
                 meta=dict(source=os.path.basename(path)))


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
