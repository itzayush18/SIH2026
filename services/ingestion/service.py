"""
OilTrace — Ingestion service.

Responsible for:
  - Registering source assets (SAR, optical, AIS files)
  - Computing and verifying checksums for data integrity
  - Basic metadata QC (CRS, timestamps, bounding box)

Scaffold pass: returns mock checksums and metadata.
"""

from __future__ import annotations

import hashlib
import os
from datetime import datetime
from typing import Optional

from packages.schemas.models import SourceAsset, AssetType


def compute_checksum(uri: str) -> str:
    """
    Compute a SHA-256 checksum of the asset at *uri*.

    Scaffold: hashes the URI string itself (no real file I/O).
    Production: would stream-hash the actual file bytes.
    """
    return hashlib.sha256(uri.encode("utf-8")).hexdigest()


def register_asset(
    case_id: str,
    asset_id: str,
    uri: str,
    asset_type: AssetType = AssetType.other,
    crs: str = "EPSG:4326",
    acquisition_time: Optional[datetime] = None,
    licence: str = "unknown",
) -> SourceAsset:
    """
    Register a new source asset to a case.

    Computes checksum, validates basic metadata, and returns
    the immutable SourceAsset record.

    Args:
        case_id: Parent case identifier.
        asset_id: Unique identifier for this asset.
        uri: Path or URL to the source data.
        asset_type: Type of asset (SAR, optical, AIS, etc.).
        crs: Coordinate reference system string.
        acquisition_time: When the data was acquired.
        licence: Data licence string.

    Returns:
        Populated SourceAsset model.
    """
    checksum = compute_checksum(uri)
    return SourceAsset(
        asset_id=asset_id,
        case_id=case_id,
        uri=uri,
        checksum=checksum,
        asset_type=asset_type,
        crs=crs,
        acquisition_time=acquisition_time or datetime.utcnow(),
        licence=licence,
    )


def validate_metadata(asset: SourceAsset) -> list[str]:
    """
    Run basic QC checks on asset metadata.

    Returns a list of warning strings (empty = all OK).

    Scaffold: checks CRS and non-empty URI only.
    """
    warnings: list[str] = []
    if not asset.uri:
        warnings.append("Asset URI is empty")
    if asset.crs.upper() not in ("EPSG:4326", "EPSG:32643", "EPSG:32644"):
        warnings.append(f"Unusual CRS: {asset.crs}")
    return warnings
