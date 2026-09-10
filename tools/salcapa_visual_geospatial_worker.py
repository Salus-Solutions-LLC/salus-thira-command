#!/usr/bin/env python3
"""Isolated, bounded extraction of source-stored image location metadata."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_EVEN
import json
import os
from pathlib import Path
import resource
import sys
import warnings


MAX_ADDRESS_SPACE = 384 * 1024 * 1024
MAX_CPU_SECONDS = 12
MAX_FILE_BYTES = 16 * 1024 * 1024
MAX_OPEN_FILES = 48
MAX_DIMENSION = 8_000
MAX_PIXELS = 16_000_000
MAX_METADATA_BYTES = 1024 * 1024
PROCESSOR = "SalCAPA Isolated Location Metadata Extractor"
PROCESSOR_VERSION = "1.0.0"
GPS_IFD = 34853


class WorkerFailure(Exception):
    def __init__(self, code: str, detail: str):
        super().__init__(detail)
        self.code = code
        self.detail = detail


def _apply_limits() -> None:
    resource.setrlimit(resource.RLIMIT_CPU, (MAX_CPU_SECONDS, MAX_CPU_SECONDS + 1))
    resource.setrlimit(resource.RLIMIT_AS, (MAX_ADDRESS_SPACE, MAX_ADDRESS_SPACE))
    resource.setrlimit(resource.RLIMIT_FSIZE, (MAX_FILE_BYTES, MAX_FILE_BYTES))
    resource.setrlimit(resource.RLIMIT_NOFILE, (MAX_OPEN_FILES, MAX_OPEN_FILES))
    os.umask(0o077)


def _text(value: object, limit: int = 200) -> str:
    result = str(value).replace("\x00", "").strip()
    if any(ord(character) < 32 for character in result):
        raise WorkerFailure("LOCATION_METADATA_INVALID", "Location metadata contains invalid control characters.")
    return result[:limit]


def _rational(value: object) -> tuple[Decimal, dict]:
    numerator = getattr(value, "numerator", None)
    denominator = getattr(value, "denominator", None)
    if numerator is None or denominator is None:
        if isinstance(value, (tuple, list)) and len(value) == 2:
            numerator, denominator = value
        else:
            try:
                decimal = Decimal(str(float(value)))
            except (TypeError, ValueError, OverflowError, InvalidOperation) as exc:
                raise WorkerFailure("LOCATION_METADATA_INVALID", "Location metadata contains an invalid numeric value.") from exc
            if not decimal.is_finite():
                raise WorkerFailure("LOCATION_METADATA_INVALID", "Location metadata contains a non-finite numeric value.")
            return decimal, {"display": format(decimal, "f"), "representation": "decoded numeric"}
    try:
        numerator_decimal = Decimal(int(numerator))
        denominator_decimal = Decimal(int(denominator))
    except (TypeError, ValueError, OverflowError, InvalidOperation) as exc:
        raise WorkerFailure("LOCATION_METADATA_INVALID", "Location metadata contains an invalid rational value.") from exc
    if denominator_decimal == 0 or abs(numerator_decimal) > Decimal(10) ** 15 or abs(denominator_decimal) > Decimal(10) ** 15:
        raise WorkerFailure("LOCATION_METADATA_INVALID", "Location metadata contains an unsafe rational value.")
    decimal = numerator_decimal / denominator_decimal
    if not decimal.is_finite():
        raise WorkerFailure("LOCATION_METADATA_INVALID", "Location metadata contains a non-finite rational value.")
    return decimal, {
        "numerator": str(int(numerator_decimal)),
        "denominator": str(int(denominator_decimal)),
        "representation": "source rational",
    }


def _dms(value: object, *, latitude: bool) -> tuple[Decimal, list[dict]]:
    if not isinstance(value, (tuple, list)) or len(value) != 3:
        raise WorkerFailure("LOCATION_METADATA_INCOMPLETE", "Location coordinates do not contain degrees, minutes, and seconds.")
    decoded = [_rational(item) for item in value]
    degrees, minutes, seconds = (item[0] for item in decoded)
    maximum = Decimal(90 if latitude else 180)
    if degrees < 0 or degrees > maximum or minutes < 0 or minutes >= 60 or seconds < 0 or seconds >= 60:
        raise WorkerFailure("LOCATION_METADATA_RANGE", "Location coordinates are outside valid degree, minute, or second ranges.")
    if degrees == maximum and (minutes != 0 or seconds != 0):
        raise WorkerFailure("LOCATION_METADATA_RANGE", "Location coordinates exceed the valid latitude or longitude boundary.")
    decimal = degrees + minutes / Decimal(60) + seconds / Decimal(3600)
    return decimal, [item[1] for item in decoded]


def _decimal_output(value: Decimal) -> str:
    return format(value.quantize(Decimal("0.00000001"), rounding=ROUND_HALF_EVEN), "f")


def _time(value: object) -> tuple[str, list[dict]]:
    if not isinstance(value, (tuple, list)) or len(value) != 3:
        raise WorkerFailure("LOCATION_METADATA_INVALID", "GPS time does not contain hour, minute, and second components.")
    decoded = [_rational(item) for item in value]
    hour, minute, second = (item[0] for item in decoded)
    if hour != hour.to_integral_value() or minute != minute.to_integral_value() or not 0 <= hour <= 23 or not 0 <= minute <= 59 or not 0 <= second < 60:
        raise WorkerFailure("LOCATION_METADATA_RANGE", "GPS time is outside the valid 24-hour range.")
    rendered = f"{int(hour):02d}:{int(minute):02d}:{format(second.normalize(), 'f').zfill(2)} UTC"
    return rendered, [item[1] for item in decoded]


def _location(exif) -> dict:
    if GPS_IFD not in exif:
        return {"status": "Location Metadata Not Present", "source_components": {}}
    try:
        gps = exif.get_ifd(GPS_IFD)
    except Exception as exc:
        raise WorkerFailure("LOCATION_METADATA_INVALID", "The GPS metadata directory could not be read safely.") from exc
    if not isinstance(gps, dict) or not gps:
        return {"status": "Location Metadata Not Present", "source_components": {}}
    allowed = {1, 2, 3, 4, 5, 6, 7, 16, 17, 18, 29, 31}
    if any(not isinstance(key, int) for key in gps):
        raise WorkerFailure("LOCATION_METADATA_INVALID", "The GPS metadata directory contains invalid tags.")
    latitude_present = 1 in gps or 2 in gps
    longitude_present = 3 in gps or 4 in gps
    if latitude_present != longitude_present or latitude_present and not all(tag in gps for tag in (1, 2, 3, 4)):
        raise WorkerFailure("LOCATION_METADATA_INCOMPLETE", "Latitude and longitude metadata must contain complete paired values.")
    components: dict[str, object] = {"available_tag_ids": sorted(key for key in gps if key in allowed)}
    result: dict[str, object] = {"status": "Location Metadata Incomplete — Human Review Needed"}
    if latitude_present:
        latitude_ref, longitude_ref = _text(gps[1], 4).upper(), _text(gps[3], 4).upper()
        if latitude_ref not in {"N", "S"} or longitude_ref not in {"E", "W"}:
            raise WorkerFailure("LOCATION_METADATA_INVALID", "Latitude or longitude direction metadata is invalid.")
        latitude, latitude_parts = _dms(gps[2], latitude=True)
        longitude, longitude_parts = _dms(gps[4], latitude=False)
        if latitude_ref == "S":
            latitude = -latitude
        if longitude_ref == "W":
            longitude = -longitude
        result.update({
            "status": "Location Metadata Present",
            "latitude_decimal": _decimal_output(latitude),
            "longitude_decimal": _decimal_output(longitude),
        })
        components.update({
            "latitude_ref": latitude_ref, "latitude_dms": latitude_parts,
            "longitude_ref": longitude_ref, "longitude_dms": longitude_parts,
            "normalization": "degrees + minutes/60 + seconds/3600; S and W are negative; eight decimal places",
        })
    if 5 in gps or 6 in gps:
        if 6 not in gps:
            raise WorkerFailure("LOCATION_METADATA_INCOMPLETE", "Altitude reference is present without an altitude value.")
        altitude, raw_altitude = _rational(gps[6])
        altitude_ref = gps.get(5, 0)
        if isinstance(altitude_ref, bytes):
            altitude_ref = altitude_ref[0] if altitude_ref else 0
        try:
            altitude_ref = int(altitude_ref)
        except (TypeError, ValueError, OverflowError) as exc:
            raise WorkerFailure("LOCATION_METADATA_INVALID", "Altitude reference metadata is invalid.") from exc
        if altitude_ref not in {0, 1}:
            raise WorkerFailure("LOCATION_METADATA_INVALID", "Altitude reference metadata is unsupported.")
        if altitude_ref == 1:
            altitude = -altitude
        result["altitude_meters"] = format(altitude.quantize(Decimal("0.001")), "f")
        components.update({"altitude_ref": altitude_ref, "altitude": raw_altitude})
    if 16 in gps or 17 in gps:
        if not all(tag in gps for tag in (16, 17)):
            raise WorkerFailure("LOCATION_METADATA_INCOMPLETE", "Image direction metadata is incomplete.")
        direction_ref = _text(gps[16], 4).upper()
        direction, raw_direction = _rational(gps[17])
        if direction_ref not in {"T", "M"} or direction < 0 or direction >= 360:
            raise WorkerFailure("LOCATION_METADATA_RANGE", "Image direction metadata is invalid or outside its valid range.")
        result["image_direction_degrees"] = format(direction.quantize(Decimal("0.001")), "f")
        components.update({"image_direction_ref": direction_ref, "image_direction": raw_direction})
    if 18 in gps:
        datum = _text(gps[18], 80)
        result["map_datum"] = datum
        components["map_datum"] = datum
    if 29 in gps:
        date = _text(gps[29], 20)
        parts = date.split(":")
        if len(parts) != 3 or not all(part.isdigit() for part in parts) or len(parts[0]) != 4:
            raise WorkerFailure("LOCATION_METADATA_INVALID", "GPS date metadata is invalid.")
        year, month, day = (int(part) for part in parts)
        try:
            import datetime as _datetime
            _datetime.date(year, month, day)
        except ValueError as exc:
            raise WorkerFailure("LOCATION_METADATA_RANGE", "GPS date metadata is outside the valid calendar range.") from exc
        result["gps_date"] = f"{day:02d} {('January','February','March','April','May','June','July','August','September','October','November','December')[month-1]} {year:04d}"
        components["gps_date_stamp"] = date
    if 7 in gps:
        rendered, raw_time = _time(gps[7])
        result["gps_time_utc"] = rendered
        components["gps_time"] = raw_time
    if 31 in gps:
        error, raw_error = _rational(gps[31])
        if error < 0:
            raise WorkerFailure("LOCATION_METADATA_RANGE", "Horizontal positioning error cannot be negative.")
        components["horizontal_positioning_error_meters"] = raw_error
    result["source_components"] = components
    return result


def extract(path: Path) -> dict:
    from PIL import Image
    from PIL.Image import DecompressionBombError, DecompressionBombWarning

    Image.MAX_IMAGE_PIXELS = MAX_PIXELS
    warnings.simplefilter("error", DecompressionBombWarning)
    if not path.is_file() or path.stat().st_size < 8 or path.stat().st_size > MAX_FILE_BYTES:
        raise WorkerFailure("IMAGE_SOURCE_LIMIT", "The image is unavailable or exceeds the bounded source-size limit.")
    header = path.read_bytes()[:16]
    expected = "JPEG" if header.startswith(b"\xff\xd8\xff") else "PNG" if header.startswith(b"\x89PNG\r\n\x1a\n") else None
    if expected is None:
        raise WorkerFailure("IMAGE_HEADER_INVALID", "The material does not contain a supported JPEG or PNG header.")
    try:
        with Image.open(path, formats=[expected]) as check:
            check.verify()
        with Image.open(path, formats=[expected]) as image:
            if image.format != expected or int(getattr(image, "n_frames", 1)) != 1 or bool(getattr(image, "is_animated", False)):
                raise WorkerFailure("IMAGE_FORMAT_INVALID", "The image format or frame count is not supported.")
            width, height = image.size
            if width < 1 or height < 1 or width > MAX_DIMENSION or height > MAX_DIMENSION or width * height > MAX_PIXELS:
                raise WorkerFailure("IMAGE_DIMENSION_LIMIT", "The image dimensions exceed the bounded processing limit.")
            exif = image.getexif()
            metadata_size = len(exif.tobytes()) if exif else 0
            if metadata_size > MAX_METADATA_BYTES:
                raise WorkerFailure("IMAGE_METADATA_LIMIT", "The image metadata exceeds the bounded processing limit.")
            orientation = exif.get(274, 1) if exif else 1
            location = _location(exif)
    except WorkerFailure:
        raise
    except (DecompressionBombError, DecompressionBombWarning, MemoryError) as exc:
        raise WorkerFailure("IMAGE_RESOURCE_LIMIT", "The image exceeded bounded processing resources.") from exc
    except Exception as exc:
        raise WorkerFailure("IMAGE_PARSE_FAILED", "The image metadata could not be decoded safely.") from exc
    return {"ok": True, "facts": {
        "processor": PROCESSOR, "processor_version": PROCESSOR_VERSION, "format": expected,
        "width": width, "height": height, "orientation_applied": orientation not in (None, 1, "1"),
        "location_metadata": location,
    }}


def main() -> None:
    _apply_limits()
    if len(sys.argv) != 2:
        print(json.dumps({"ok": False, "code": "WORKER_INPUT_INVALID", "detail": "The location-metadata worker received invalid input."}))
        raise SystemExit(2)
    try:
        result = extract(Path(sys.argv[1]))
    except WorkerFailure as exc:
        print(json.dumps({"ok": False, "code": exc.code, "detail": exc.detail}, separators=(",", ":")))
        raise SystemExit(2)
    except (MemoryError, RecursionError):
        print(json.dumps({"ok": False, "code": "IMAGE_RESOURCE_LIMIT", "detail": "The image exceeded bounded processing resources."}, separators=(",", ":")))
        raise SystemExit(2)
    except Exception:
        print(json.dumps({"ok": False, "code": "WORKER_FAILED", "detail": "Location metadata could not be read safely."}, separators=(",", ":")))
        raise SystemExit(2)
    print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))


if __name__ == "__main__":
    main()
